#!/usr/bin/env python3
"""
MeterSphere 辅助工具 — 供 AI Agent 在测试用例同步和测试计划管理中使用

提供子命令：
  ping               检查 MeterSphere 连通性
  list-modules       获取用例模块树
  ensure-module      查找或创建子模块
  import-cases       按 module 字段分组导入用例（自动创建子模块 + 打标签，支持按需求名建父模块）
  list-stages        获取测试计划阶段选项
  find-or-create-plan 按名称查找或创建测试计划（限定 AI 工作流分类）
  add-cases-to-plan  将用例关联到测试计划
  list-plan-cases    查询测试计划中的用例
  update-case-result 更新测试计划用例执行结果
  batch-update-results 批量更新测试计划用例执行结果

用法:
    python3 metersphere_helper.py ping
    python3 metersphere_helper.py list-modules [--parent-id ID]
    python3 metersphere_helper.py ensure-module <parent_id> <name>
    python3 metersphere_helper.py import-cases <parent_module_id> <cases.json> [--requirement <需求名>]
    python3 metersphere_helper.py list-stages
    python3 metersphere_helper.py find-or-create-plan <plan_name> [--stage smoke]
    python3 metersphere_helper.py add-cases-to-plan <plan_id> --case-ids id1,id2,...
    python3 metersphere_helper.py list-plan-cases <plan_id>
    python3 metersphere_helper.py update-case-result <plan_case_id> <Pass|Failure|Prepare> [--actual-result TEXT] [--comment TEXT]
    python3 metersphere_helper.py batch-update-results <plan_id> --results-json <file>

配置:
    所有配置通过 .env 文件加载（同目录），环境变量存在时覆盖。

环境变量（必须设置）:
    MS_ACCESS_KEY          - API 认证 key
    MS_SECRET_KEY          - AES 签名 key

环境变量（实例配置）:
    MS_BASE_URL            - MeterSphere 地址
    MS_PROJECT_ID          - 项目 UUID
    MS_WORKSPACE_ID        - 工作空间 UUID
    MS_DEFAULT_NODE_ID     - 用例库父模块 ID（AI 工作流）
    MS_PLAN_NODE_ID        - 测试计划分类节点 ID（AI 工作流）
    MS_DEFAULT_MAINTAINER  - 默认负责人（默认 admin）
    MS_DEFAULT_STAGE       - 默认测试计划阶段（默认 smoke）

环境变量（自定义字段 ID）:
    MS_FIELD_ID_MAINTAINER - 责任人字段 ID
    MS_FIELD_ID_PRIORITY   - 用例等级字段 ID
    MS_FIELD_ID_STATUS     - 用例状态字段 ID
    MS_FIELD_ID_AUTOMATED  - 是否已自动化字段 ID
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
import uuid
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

# ==================== 配置 ====================

_REQUIRED_ENV = ('MS_ACCESS_KEY', 'MS_SECRET_KEY')
_missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
if _missing:
    print(f"ERROR: missing required environment variables: {', '.join(_missing)}", file=sys.stderr)
    print("Set them via .env file or: export MS_ACCESS_KEY=xxx MS_SECRET_KEY=xxx", file=sys.stderr)
    sys.exit(1)


def _cfg(key: str, default: str = '') -> str:
    return os.environ.get(key, default)


def _field_id(name: str) -> str:
    """Get MeterSphere custom field ID from env var MS_FIELD_ID_<NAME>."""
    return os.environ.get(f'MS_FIELD_ID_{name.upper()}', '')


# ==================== AES 签名 ====================

try:
    from Crypto.Cipher import AES as _AES
except ImportError:
    _AES = None


def _aes_encrypt(text: str, secret_key: str, iv: str) -> bytes:
    """AES-CBC 加密（移植自 ai-case utils.py）"""
    if _AES is None:
        print("错误: 需要 pycryptodome 库。请执行: pip install pycryptodome", file=sys.stderr)
        sys.exit(1)

    block_size = _AES.block_size
    pad = lambda s: s + (block_size - len(s) % block_size) * chr(block_size - len(s) % block_size)
    cipher = _AES.new(secret_key.encode('UTF-8'), _AES.MODE_CBC, iv.encode('UTF-8'))
    encrypted = cipher.encrypt(pad(text).encode('UTF-8'))
    return base64.b64encode(encrypted)


def _get_signature() -> str:
    ak = _cfg('MS_ACCESS_KEY')
    sk = _cfg('MS_SECRET_KEY')
    timestamp = int(round(time.time() * 1000))
    combo = f"{ak}|{uuid.uuid4()}|{timestamp}"
    return _aes_encrypt(combo, sk, ak).decode('utf-8')


# ==================== HTTP 请求 ====================

_ssl_ctx = ssl.create_default_context()
MAX_RETRIES = 2
RETRY_DELAY = 1


def _request(method: str, path: str, payload: dict | None = None,
             *, files: dict | None = None, retries: int = MAX_RETRIES) -> Any:
    """发送带签名的 HTTP 请求到 MeterSphere API"""
    url = f"{_cfg('MS_BASE_URL')}{path}"

    for attempt in range(retries + 1):
        headers = {
            'accessKey': _cfg('MS_ACCESS_KEY'),
            'signature': _get_signature(),
            'Accept': 'application/json',
        }

        if files:
            # multipart/form-data for case creation
            boundary = f'----MSBoundary{uuid.uuid4().hex[:16]}'
            headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
            parts = []
            for name, (filename, content, content_type) in files.items():
                parts.append(f'--{boundary}\r\n'.encode())
                parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
                parts.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
                parts.append(content if isinstance(content, bytes) else content.encode('utf-8'))
                parts.append(b'\r\n')
            parts.append(f'--{boundary}--\r\n'.encode())
            data = b''.join(parts)
        elif payload is not None:
            headers['Content-Type'] = 'application/json;charset=UTF-8'
            data = json.dumps(payload).encode('utf-8')
        else:
            data = None

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if isinstance(result, dict) and result.get('success') is False:
                    msg = result.get('message', '')
                    raise RuntimeError(f"MeterSphere API 错误: {msg}")
                return result.get('data') if isinstance(result, dict) and 'data' in result else result
        except (urllib.error.URLError, OSError) as exc:
            if attempt < retries and not isinstance(exc, urllib.error.HTTPError):
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            if isinstance(exc, urllib.error.HTTPError):
                body_text = exc.read().decode('utf-8', errors='replace')[:500]
                raise RuntimeError(f"HTTP {exc.code}: {body_text}") from exc
            raise RuntimeError(f"网络请求失败: {exc}") from exc

    raise RuntimeError("请求失败（已重试）")


# ==================== 用例格式转换 ====================

MAX_CASE_NAME_LENGTH = 250
VALID_PRIORITIES = frozenset({'P0', 'P1', 'P2', 'P3'})
_TITLE_NOISE = re.compile(
    r'\s*[(\[（【]\s*(?:AC|ac|Ac|RP|rp|Rp|CP|cp|TC|tc)\s*[-—]\s*\d+\s*[)\]）】]'
)


def _sanitize_title(title: str) -> str:
    return _TITLE_NOISE.sub('', title).strip()


def _sanitize_quotes(text: str) -> str:
    if not isinstance(text, str) or '"' not in text:
        return text
    result, opening = [], True
    for ch in text:
        if ch == '"':
            result.append('「' if opening else '」')
            opening = not opening
        else:
            result.append(ch)
    return ''.join(result)


def _convert_case(raw: dict) -> dict | None:
    """将 AI 生成的用例转为 MS API 格式"""
    steps_raw = raw.get('steps', [])
    if steps_raw and isinstance(steps_raw[0], dict):
        if 'desc' in steps_raw[0]:
            ms_steps = [{'num': s.get('num', i+1),
                         'desc': _sanitize_quotes(s.get('desc', '')),
                         'result': _sanitize_quotes(s.get('result') or s.get('expected', ''))}
                        for i, s in enumerate(steps_raw)]
        else:
            ms_steps = [{'num': i+1,
                         'desc': _sanitize_quotes(s.get('action', '')),
                         'result': _sanitize_quotes(s.get('expected', ''))}
                        for i, s in enumerate(steps_raw)]
    else:
        expected_raw = raw.get('expected', [])
        ms_steps = [{'num': i+1,
                     'desc': _sanitize_quotes(str(s)),
                     'result': _sanitize_quotes(str(expected_raw[i]) if i < len(expected_raw) else '')}
                    for i, s in enumerate(steps_raw)]

    valid_steps = [s for s in ms_steps if s.get('desc', '').strip()]
    if not valid_steps:
        return None

    precond = raw.get('preconditions', raw.get('prerequisite', ''))
    if isinstance(precond, list):
        precond = '\n'.join(precond)

    name = _sanitize_title(raw.get('title', raw.get('name', ''))).strip()
    if not name:
        return None
    if len(name) > MAX_CASE_NAME_LENGTH:
        name = name[:MAX_CASE_NAME_LENGTH] + '…'

    priority = raw.get('priority', 'P2')
    if priority not in VALID_PRIORITIES:
        priority = 'P2'

    return {
        'name': name,
        'priority': priority,
        'prerequisite': _sanitize_quotes(precond),
        'steps': valid_steps,
        'tags': ['AI 用例生成'],
    }


def _dedup_names(cases: list[dict]) -> int:
    counts: dict[str, int] = {}
    for c in cases:
        n = c['name']
        counts[n] = counts.get(n, 0) + 1
    dups = {n for n, cnt in counts.items() if cnt > 1}
    if not dups:
        return 0
    seq: dict[str, int] = {}
    fixed = 0
    for c in cases:
        n = c['name']
        if n in dups:
            s = seq.get(n, 0) + 1
            seq[n] = s
            if s > 1:
                c['name'] = f"{n}_{s}"
                fixed += 1
    return fixed


# ==================== 模块管理 ====================

_module_cache: list | None = None


def _get_modules() -> list:
    global _module_cache
    if _module_cache is not None:
        return _module_cache
    _module_cache = _request('POST', f"/track/case/node/list/{_cfg('MS_PROJECT_ID')}",
                             payload={'casePublic': False}) or []
    return _module_cache


def _invalidate_cache():
    global _module_cache
    _module_cache = None


def _find_child(nodes: list, parent_id: str, name: str) -> dict | None:
    """在模块树中查找 parent_id 下名为 name 的直接子节点"""
    def find_parent(ns):
        for n in ns:
            if n.get('id') == parent_id:
                return n
            children = n.get('children') or []
            found = find_parent(children)
            if found:
                return found
        return None

    parent = find_parent(nodes)
    if not parent:
        return None
    for child in parent.get('children') or []:
        if child.get('name') == name:
            return {'id': child['id'], 'name': name, 'parent_id': parent_id}
    return None


def _resolve_level(parent_id: str) -> int:
    """根据父模块 ID 计算子模块层级"""
    def find_level(nodes, target, level=1):
        for n in nodes:
            if n.get('id') == target:
                return level
            children = n.get('children') or []
            found = find_level(children, target, level + 1)
            if found:
                return found
        return 0
    level = find_level(_get_modules(), parent_id)
    return (level + 1) if level > 0 else 2


def _ensure_module(parent_id: str, name: str) -> dict:
    """查找或创建单层子模块，返回包含 is_new 标志的结果"""
    existing = _find_child(_get_modules(), parent_id, name)
    if existing:
        existing['is_new'] = False
        return existing
    module_id = _request('POST', '/track/case/node/add', payload={
        'level': _resolve_level(parent_id),
        'type': 'add',
        'parentId': parent_id,
        'name': name,
        'label': name,
        'projectId': _cfg('MS_PROJECT_ID'),
    })
    _invalidate_cache()
    return {'id': str(module_id), 'name': name, 'parent_id': parent_id, 'is_new': True}


def _ensure_module_path(parent_id: str, path: str) -> tuple[dict, int]:
    """按 '/' 分隔的路径逐层创建模块，返回 (叶子模块信息, 新建模块数)"""
    parts = [p.strip() for p in path.split('/') if p.strip()]
    if not parts:
        parts = ['未分组']
    created = 0
    current_parent = parent_id
    result = None
    for part in parts:
        result = _ensure_module(current_parent, part)
        if result.get('is_new'):
            created += 1
        current_parent = result['id']
    return result, created


def _get_module_path(module_id: str) -> str:
    """获取模块的完整路径"""
    def find_path(nodes, target, prefix=''):
        for n in nodes:
            p = f"{prefix}/{n.get('name', '')}"
            if n.get('id') == target:
                return p
            children = n.get('children') or []
            found = find_path(children, target, p)
            if found:
                return found
        return None
    return find_path(_get_modules(), module_id) or '/未规划用例'


# ==================== 用例创建 ====================

def _add_case(module_id: str, case_data: dict, module_path: str = '') -> Any:
    """创建单条测试用例（multipart/form-data）"""
    if not module_path:
        module_path = _get_module_path(module_id)

    maintainer = _cfg('MS_DEFAULT_MAINTAINER', 'admin')
    priority = case_data.get('priority', 'P2')
    payload = {
        'name': case_data['name'],
        'num': '',
        'nodePath': module_path,
        'maintainer': maintainer,
        'priority': priority,
        'type': 'functional',
        'method': '',
        'prerequisite': case_data.get('prerequisite', ''),
        'testId': '[]',
        'nodeId': module_id,
        'steps': json.dumps(case_data.get('steps', []), ensure_ascii=False),
        'stepDesc': '',
        'stepResult': '',
        'selected': [],
        'remark': '',
        'tags': json.dumps(case_data.get('tags', []), ensure_ascii=False),
        'demandId': '',
        'demandName': '',
        'status': 'Prepare',
        'reviewStatus': 'Prepare',
        'stepDescription': '',
        'expectedResult': '',
        'stepModel': 'STEP',
        'customNum': '',
        'followPeople': '',
        'versionId': '',
        'id': None,
        'casePublic': False,
        'projectId': _cfg('MS_PROJECT_ID'),
        'addFields': [
            {'fieldId': _field_id('maintainer'), 'value': f'"{maintainer}"'},
            {'fieldId': _field_id('priority'), 'value': f'"{priority}"'},
            {'fieldId': _field_id('status'), 'value': '"Prepare"'},
            {'fieldId': _field_id('automated'), 'value': '""'},
        ],
        'editFields': [],
        'requestFields': [
            {'id': _field_id('maintainer'), 'name': '责任人', 'customData': None, 'type': 'member', 'value': maintainer},
            {'id': _field_id('priority'), 'name': '用例等级', 'customData': None, 'type': 'select', 'value': priority},
            {'id': _field_id('status'), 'name': '用例状态', 'customData': None, 'type': 'select', 'value': 'Prepare'},
            {'id': _field_id('automated'), 'name': '是否已自动化', 'customData': None, 'type': 'radio', 'value': ''},
        ],
        'fields': [],
        'follows': [],
    }
    content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return _request('POST', '/track/test/case/add',
                    files={'request': ('blob', content, 'application/json')})


# ==================== 测试计划管理 ====================

def _find_plan_by_name(name: str) -> dict | None:
    """在 AI 工作流分类下按名称搜索测试计划"""
    result = _request('POST', '/track/test/plan/list/1/50', payload={
        'projectId': _cfg('MS_PROJECT_ID'),
        'nodeIds': [_cfg('MS_PLAN_NODE_ID')],
        'name': name,
    }) or {}
    plans = result.get('listObject', [])
    # 精确匹配
    for p in plans:
        if p.get('name') == name:
            return p
    return None


def _create_plan(name: str, stage: str = '') -> dict:
    """创建测试计划（归类到 AI 工作流节点）"""
    if not stage:
        stage = _cfg('MS_DEFAULT_STAGE', 'smoke')
    return _request('POST', '/track/test/plan/add', payload={
        'name': name,
        'projectId': _cfg('MS_PROJECT_ID'),
        'workspaceId': _cfg('MS_WORKSPACE_ID'),
        'stage': stage,
        'status': 'Prepare',
        'principals': [_cfg('MS_DEFAULT_MAINTAINER', 'admin')],
        'follows': [],
        'projectIds': [_cfg('MS_PROJECT_ID')],
        'automaticStatusUpdate': False,
        'repeatCase': False,
        'nodeId': _cfg('MS_PLAN_NODE_ID'),
        'nodePath': '/AI 工作流',
        'tags': '[]',
        'description': 'AI 工作流自动创建',
    })


def _add_cases_to_plan(plan_id: str, case_ids: list[str]) -> None:
    """将用例关联到测试计划"""
    if not case_ids:
        return
    _request('POST', '/track/test/plan/relevance', payload={
        'planId': plan_id,
        'executor': _cfg('MS_DEFAULT_MAINTAINER', 'admin'),
        'ids': case_ids,
        'testCaseIds': case_ids,
        'request': {'projectId': _cfg('MS_PROJECT_ID')},
        'checked': False,
    })


def _list_plan_cases(plan_id: str, page: int = 1, page_size: int = 100) -> dict:
    """查询测试计划中的用例"""
    return _request('POST', f'/track/test/plan/case/list/{page}/{page_size}', payload={
        'planId': plan_id,
        'projectId': _cfg('MS_PROJECT_ID'),
    }) or {}


def _update_case_result(plan_case_id: str, status: str,
                        actual_result: str = '', comment: str = '') -> Any:
    """更新测试计划用例执行结果"""
    payload: dict[str, Any] = {'id': plan_case_id, 'status': status}
    if actual_result:
        payload['actualResult'] = actual_result
    if comment:
        payload['comment'] = comment
    return _request('POST', '/track/test/plan/case/edit', payload=payload)


# ==================== 子命令实现 ====================

def cmd_ping():
    """检查 MeterSphere 连通性"""
    try:
        modules = _get_modules()
        count = sum(1 for _ in _iter_all_nodes(modules))
        print(json.dumps({
            'status': 'ok',
            'base_url': _cfg('MS_BASE_URL'),
            'project_id': _cfg('MS_PROJECT_ID'),
            'module_count': count,
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


def _iter_all_nodes(nodes):
    for n in nodes:
        yield n
        yield from _iter_all_nodes(n.get('children') or [])


def cmd_list_modules(parent_id: str = ''):
    """获取模块树"""
    modules = _get_modules()
    if parent_id:
        def find(ns):
            for n in ns:
                if n.get('id') == parent_id:
                    return n.get('children') or []
                found = find(n.get('children') or [])
                if found is not None:
                    return found
            return None
        modules = find(modules) or []

    def simplify(nodes):
        return [{'id': n['id'], 'name': n.get('name', ''),
                 'case_count': n.get('caseNum', 0),
                 'children': simplify(n.get('children') or [])}
                for n in nodes]

    print(json.dumps(simplify(modules), ensure_ascii=False, indent=2))


def cmd_ensure_module(parent_id: str, name: str):
    """查找或创建子模块"""
    result = _ensure_module(parent_id, name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_import_cases(parent_module_id: str, cases_file: str, requirement_name: str = ''):
    """按 module 字段分组导入用例，可选按需求名创建父模块"""
    if not parent_module_id:
        parent_module_id = _cfg('MS_DEFAULT_NODE_ID')

    # 如果指定了需求名，先创建需求级父模块，子模块挂在其下
    modules_created = 0
    if requirement_name:
        req_module = _ensure_module(parent_module_id, requirement_name)
        parent_module_id = req_module['id']
        if req_module.get('is_new'):
            modules_created += 1

    with open(cases_file, 'r', encoding='utf-8') as f:
        raw_cases = json.load(f)

    if isinstance(raw_cases, dict):
        raw_cases = raw_cases.get('cases', raw_cases.get('test_cases', [raw_cases]))

    # 转换并按 module 分组
    by_module: dict[str, list[dict]] = {}
    skipped = 0
    for raw in raw_cases:
        converted = _convert_case(raw)
        if not converted:
            skipped += 1
            continue
        module_name = raw.get('module', '未分组')
        by_module.setdefault(module_name, []).append(converted)

    # 去重
    for cases in by_module.values():
        _dedup_names(cases)

    # 逐模块创建子模块（顺序，避免并发创建重复模块）
    total_imported = 0
    total_failed = 0
    case_mapping = []
    module_meta: dict[str, tuple[str, str]] = {}  # module_name → (module_id, module_path)

    for module_name in by_module:
        module_info, created = _ensure_module_path(parent_module_id, module_name)
        module_id = module_info['id']
        module_path = _get_module_path(module_id)
        module_meta[module_name] = (module_id, module_path)
        modules_created += created

    # 并发导入用例
    def _import_one(module_name: str, case_data: dict) -> dict | None:
        module_id, module_path = module_meta[module_name]
        local_id = case_data.get('case_id', case_data['name'])
        try:
            result = _add_case(module_id, case_data, module_path=module_path)
            ms_id = ''
            if isinstance(result, dict):
                ms_id = str(result.get('id', ''))
            elif result is not None:
                ms_id = str(result)
            return {'local_id': local_id, 'ms_id': ms_id, 'module': module_name, 'name': case_data['name']}
        except Exception as e:
            print(f"导入失败: {case_data['name']}: {e}", file=sys.stderr)
            return None

    tasks = [(mn, cd) for mn, cases in by_module.items() for cd in cases]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_import_one, mn, cd): (mn, cd) for mn, cd in tasks}
        for future in as_completed(futures):
            result = future.result()
            if result:
                case_mapping.append(result)
                total_imported += 1
            else:
                total_failed += 1

    report = {
        'imported': total_imported,
        'failed': total_failed,
        'skipped': skipped,
        'modules_created': modules_created,
        'case_mapping': case_mapping,
        'metersphere_url': (
            f"{_cfg('MS_BASE_URL')}/#/track/case/all/{_cfg('MS_PROJECT_ID')}"
            f"?moduleId={parent_module_id}"
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_list_stages():
    """获取测试计划阶段选项"""
    result = _request('GET', f"/track/test/plan/get/stage/option/{_cfg('MS_PROJECT_ID')}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_find_or_create_plan(plan_name: str, stage: str = 'smoke'):
    """按名称查找或创建测试计划"""
    existing = _find_plan_by_name(plan_name)
    if existing:
        plan_id = existing['id']
        print(json.dumps({
            'plan_id': plan_id,
            'plan_name': existing['name'],
            'plan_url': f"{_cfg('MS_BASE_URL')}/#/track/plan/view/{plan_id}",
            'is_new': False,
            'status': existing.get('status', ''),
        }, ensure_ascii=False, indent=2))
        return

    plan = _create_plan(plan_name, stage)
    plan_id = plan['id'] if isinstance(plan, dict) else str(plan)
    print(json.dumps({
        'plan_id': plan_id,
        'plan_name': plan_name,
        'plan_url': f"{_cfg('MS_BASE_URL')}/#/track/plan/view/{plan_id}",
        'is_new': True,
        'status': 'Prepare',
    }, ensure_ascii=False, indent=2))


def cmd_add_cases_to_plan(plan_id: str, case_ids_str: str):
    """将用例关联到测试计划"""
    case_ids = [cid.strip() for cid in case_ids_str.split(',') if cid.strip()]
    if not case_ids:
        print('{"error": "no case IDs provided"}', file=sys.stderr)
        sys.exit(1)
    _add_cases_to_plan(plan_id, case_ids)
    print(json.dumps({
        'plan_id': plan_id,
        'added_count': len(case_ids),
    }, ensure_ascii=False, indent=2))


def cmd_list_plan_cases(plan_id: str):
    """查询测试计划中的用例"""
    all_cases = []
    page = 1
    while True:
        result = _list_plan_cases(plan_id, page=page, page_size=100)
        cases = result.get('listObject', [])
        total = result.get('itemCount', 0)
        for c in cases:
            all_cases.append({
                'id': c.get('id', ''),
                'case_id': c.get('caseId', ''),
                'name': c.get('name', ''),
                'status': c.get('status', ''),
                'priority': c.get('priority', ''),
                'executor': c.get('executor', ''),
                'node_path': c.get('nodePath', ''),
            })
        if len(all_cases) >= total or not cases:
            break
        page += 1

    print(json.dumps({
        'plan_id': plan_id,
        'total': len(all_cases),
        'cases': all_cases,
    }, ensure_ascii=False, indent=2))


def cmd_update_case_result(plan_case_id: str, status: str,
                           actual_result: str = '', comment: str = ''):
    """更新测试计划用例执行结果"""
    valid = {'Pass', 'Failure', 'Blocked', 'Skip', 'Prepare'}
    if status not in valid:
        print(f'{{"error": "status must be one of: {valid}"}}', file=sys.stderr)
        sys.exit(1)
    result = _update_case_result(plan_case_id, status, actual_result, comment)
    print(json.dumps({
        'plan_case_id': plan_case_id,
        'status': status,
        'result': result,
    }, ensure_ascii=False, indent=2))


def cmd_batch_update_results(plan_id: str, results_file: str):
    """批量更新测试计划用例执行结果"""
    with open(results_file, 'r', encoding='utf-8') as f:
        updates = json.load(f)

    if not isinstance(updates, list):
        updates = updates.get('results', [])

    success = 0
    failed = 0

    def _do_update(item):
        pcid = item.get('plan_case_id', '')
        try:
            _update_case_result(pcid, item.get('status', ''),
                                item.get('actual_result', ''), item.get('comment', ''))
            return True
        except Exception as e:
            print(f"更新失败: {pcid}: {e}", file=sys.stderr)
            return False

    with ThreadPoolExecutor(max_workers=5) as executor:
        for ok in executor.map(_do_update, updates):
            if ok:
                success += 1
            else:
                failed += 1

    print(json.dumps({
        'plan_id': plan_id,
        'total': len(updates),
        'success': success,
        'failed': failed,
    }, ensure_ascii=False, indent=2))


# ==================== CLI 入口 ====================

def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == 'ping':
            cmd_ping()
        elif cmd == 'list-modules':
            parent = ''
            if '--parent-id' in args:
                idx = args.index('--parent-id')
                parent = args[idx + 1]
            cmd_list_modules(parent)
        elif cmd == 'ensure-module':
            if len(args) < 2:
                print("用法: ensure-module <parent_id> <name>", file=sys.stderr)
                sys.exit(1)
            cmd_ensure_module(args[0], args[1])
        elif cmd == 'import-cases':
            if len(args) < 2:
                print("用法: import-cases <parent_module_id> <cases.json> [--requirement <需求名>]", file=sys.stderr)
                sys.exit(1)
            req_name = ''
            if '--requirement' in args:
                idx = args.index('--requirement')
                req_name = args[idx + 1]
            cmd_import_cases(args[0], args[1], requirement_name=req_name)
        elif cmd == 'list-stages':
            cmd_list_stages()
        elif cmd == 'find-or-create-plan':
            if len(args) < 1:
                print("用法: find-or-create-plan <plan_name> [--stage smoke]", file=sys.stderr)
                sys.exit(1)
            stage = 'smoke'
            if '--stage' in args:
                idx = args.index('--stage')
                stage = args[idx + 1]
                args = args[:idx] + args[idx+2:]
            cmd_find_or_create_plan(args[0], stage)
        elif cmd == 'add-cases-to-plan':
            if len(args) < 3 or args[1] != '--case-ids':
                print("用法: add-cases-to-plan <plan_id> --case-ids id1,id2,...", file=sys.stderr)
                sys.exit(1)
            cmd_add_cases_to_plan(args[0], args[2])
        elif cmd == 'list-plan-cases':
            if len(args) < 1:
                print("用法: list-plan-cases <plan_id>", file=sys.stderr)
                sys.exit(1)
            cmd_list_plan_cases(args[0])
        elif cmd == 'update-case-result':
            if len(args) < 2:
                print("用法: update-case-result <plan_case_id> <status> [--actual-result TEXT] [--comment TEXT]",
                      file=sys.stderr)
                sys.exit(1)
            actual = ''
            comment = ''
            if '--actual-result' in args:
                idx = args.index('--actual-result')
                actual = args[idx + 1]
            if '--comment' in args:
                idx = args.index('--comment')
                comment = args[idx + 1]
            cmd_update_case_result(args[0], args[1], actual, comment)
        elif cmd == 'batch-update-results':
            if len(args) < 3 or args[1] != '--results-json':
                print("用法: batch-update-results <plan_id> --results-json <file>", file=sys.stderr)
                sys.exit(1)
            cmd_batch_update_results(args[0], args[2])
        else:
            print(f"未知命令: {cmd}", file=sys.stderr)
            print(__doc__, file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
