#!/usr/bin/env python3
"""
MeterSphere 辅助工具 — 供 AI Agent 在测试用例同步和测试计划管理中使用

提供子命令：
  ping                 检查 MeterSphere 连通性
  list-modules         获取用例模块树
  ensure-module        查找或创建子模块
  import-cases         按 module 字段分组导入用例（自动创建子模块 + 打标签，支持按需求名建父模块）
  list-stages          获取测试计划阶段选项
  find-or-create-plan  按名称查找或创建测试计划（限定 AI 工作流分类）
  add-cases-to-plan    将用例关联到测试计划
  list-plan-cases      查询测试计划中的用例
  update-case-result   更新测试计划用例执行结果
  batch-update-results 批量更新测试计划用例执行结果
  validate-fv          按 schema 校验 forward_verification.json
  lookup-plan-case     按 case_id 三级查找 plan_case_id
  refresh-mapping      刷新/比对 ms_case_mapping.json 与 final_cases.json
  rebuild-mapping      从 MS plan 反向重建 ms_case_mapping.json（切换 plan 后用）
  writeback-from-fv    一站式：fv → MS plan 状态回写（含 P6 状态映射）

响应契约（统一）：
  exit 0  → 成功，stdout 是裸 JSON（每个命令各自语义）
  exit 1  → 运行时失败，stderr 是 JSON {type, message, retriable, ...extra}
  exit 2  → 入参/校验错（validation），stderr 同上

用法:
    python3 metersphere_helper.py ping
    python3 metersphere_helper.py list-modules [--parent-id ID]
    python3 metersphere_helper.py ensure-module <parent_id> <name>
    python3 metersphere_helper.py import-cases <parent_module_id> <cases.json> \\
      [--requirement <需求名>] [--tags 'AI 变更分析'] [--mapping-out PATH]
    python3 metersphere_helper.py list-stages
    python3 metersphere_helper.py find-or-create-plan <plan_name> [--stage smoke]
    python3 metersphere_helper.py add-cases-to-plan <plan_id> --case-ids id1,id2,...
    python3 metersphere_helper.py list-plan-cases <plan_id>
    python3 metersphere_helper.py update-case-result <plan_case_id> <Pass|Failure|Prepare> \\
      [--actual-result TEXT] [--comment TEXT]
    python3 metersphere_helper.py batch-update-results <plan_id> --results-json <file>
    python3 metersphere_helper.py validate-fv <fv.json> [--schema-path PATH] [--repo-root PATH]
    python3 metersphere_helper.py lookup-plan-case --plan-id <id> --case-id <local_id> \\
      [--mapping-path PATH]
    python3 metersphere_helper.py refresh-mapping --mapping-path PATH --cases-path final_cases.json \\
      [--diff-only|--apply]
    python3 metersphere_helper.py rebuild-mapping --plan-id <id> --cases-path final_cases.json \\
      [--mapping-out PATH]
    python3 metersphere_helper.py writeback-from-fv --plan-id <id> --fv-path <fv.json> \\
      [--mapping-path PATH] [--report-path PATH] [--dry-run]

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
from typing import Any, NoReturn

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on shell env


# ==================== 统一失败出口（P4 契约） ====================
#
# 调用方约定：
#   exit 0  → 成功，stdout 是裸 JSON（每个命令各自语义）
#   exit 1  → 运行时失败，stderr 是 JSON {type, message, retriable, ...extra}
#   exit 2  → 入参/校验错（validation），stderr 同上
#
# 详细响应表见 plugins/test/skills/metersphere-sync/SKILL.md 「Helper Commands」节。

ERR_VALIDATION = 'validation'                  # 入参非法 → exit 2
ERR_API = 'api_error'                          # MS 4xx/5xx → exit 1
ERR_NETWORK = 'network'                        # 连不上/超时 → exit 1, retriable=True
ERR_NOT_FOUND = 'not_found'                    # 资源/记录找不到 → exit 1
ERR_PRECONDITION = 'precondition_failed'      # 前置条件不满足 → exit 1
ERR_STALE_MAPPING = 'stale_mapping'            # mapping sha 与 cases 不一致 → exit 1
ERR_AMBIGUOUS = 'ambiguous'                    # 匹配歧义（重名等） → exit 1
ERR_DEPENDENCY_MISSING = 'dependency_missing'  # 缺少 Python 库等 → exit 1


class HelperError(Exception):
    """raise 而不是 sys.exit，让 writeback 等内部循环能 per-item 捕获并继续 / 重试。

    顶层 main() 捕获后转 JSON stderr + 正确 exit code。所有 cmd_* 失败都走这个。
    """

    def __init__(self, error_type: str, message: str, *,
                 retriable: bool = False, exit_code: int = 1, **extra):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.retriable = retriable
        self.exit_code = exit_code
        self.extra = extra

    def to_payload(self) -> dict:
        payload = {'type': self.error_type, 'message': self.message,
                   'retriable': self.retriable}
        payload.update(self.extra)
        return payload


def _fail(error_type: str, message: str, *,
          retriable: bool = False, exit_code: int = 1, **extra) -> 'NoReturn':
    """统一失败出口：抛 HelperError，由 main() 转 stderr+exit。"""
    raise HelperError(error_type, message,
                      retriable=retriable, exit_code=exit_code, **extra)


# ==================== 配置 ====================

_REQUIRED_ENV = ('MS_ACCESS_KEY', 'MS_SECRET_KEY')
_missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
if _missing:
    # 模块级 fail 不能用 _fail（_fail 抛 HelperError，这里没有 try/except）
    print(json.dumps({
        'type': ERR_PRECONDITION,
        'message': f"missing required environment variables: {', '.join(_missing)}",
        'retriable': False,
        'hint': 'Set via .env file or: export MS_ACCESS_KEY=xxx MS_SECRET_KEY=xxx',
        'missing': _missing,
    }, ensure_ascii=False), file=sys.stderr)
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
        _fail(ERR_DEPENDENCY_MISSING,
              "需要 pycryptodome 库。请执行: pip install pycryptodome")

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
                    # MS 业务层错误（HTTP 200 但 success=false）→ 不可重试
                    _fail(ERR_API, f"MeterSphere API 错误: {msg}",
                          retriable=False, http_status=200, path=path, method=method)
                return result.get('data') if isinstance(result, dict) and 'data' in result else result
        except (urllib.error.URLError, OSError) as exc:
            if attempt < retries and not isinstance(exc, urllib.error.HTTPError):
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            if isinstance(exc, urllib.error.HTTPError):
                body_text = exc.read().decode('utf-8', errors='replace')[:500]
                # 5xx 可重试，4xx 不可
                is_retriable = 500 <= exc.code < 600
                _fail(ERR_API, f"HTTP {exc.code}: {body_text}",
                      retriable=is_retriable, http_status=exc.code, path=path, method=method)
            # 网络错误（DNS、连接拒绝、超时等）→ 可重试
            _fail(ERR_NETWORK, f"网络请求失败: {exc}",
                  retriable=True, path=path, method=method)

    _fail(ERR_NETWORK, "请求失败（已重试）", retriable=True, path=path, method=method)


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


CONVENTIONS_DOC = 'plugins/test/CONVENTIONS.md#用例-json-格式'

# 顶层允许的字段（其他视为拼写错误）
_ALLOWED_CASE_FIELDS = frozenset({
    'title', 'priority', 'preconditions', 'steps',
    'case_id', 'module', 'test_method', 'confidence', 'review_confidence', 'source',
})
_ALLOWED_STEP_FIELDS = frozenset({'action', 'expected'})
# MS 内部格式（后端二次转换的回流）允许的步骤字段
_ALLOWED_MS_STEP_FIELDS = frozenset({'num', 'desc', 'result'})


def _validate_case_schema(raw: Any, idx: int) -> list[str]:
    """严格 schema 校验，与 ai-case case_schema.TestCase 行为对齐。

    返回错误消息列表，空表示通过。规则：
    - 必填：title / priority / preconditions / steps
    - steps 必须是 [{action, expected}] 配对对象数组（不接受字符串数组）
    - 拒绝旧字段：name / prerequisite / 顶层 expected / tags
    - 拒绝拼写错误的未知字段
    """
    errors: list[str] = []
    prefix = f'[{idx}]'
    if not isinstance(raw, dict):
        return [f'{prefix} 用例必须是对象，收到 {type(raw).__name__}']

    title_for_log = raw.get('title') or '<未命名>'
    prefix = f'[{idx}] {title_for_log}'

    # 旧字段拒绝
    if 'name' in raw and 'title' not in raw:
        errors.append(f'{prefix}: 字段 name 不被接受，必须使用 title。详见 {CONVENTIONS_DOC}')
    if 'prerequisite' in raw and 'preconditions' not in raw:
        errors.append(f'{prefix}: 字段 prerequisite 不被接受，必须使用 preconditions（字符串数组）。详见 {CONVENTIONS_DOC}')
    if 'expected' in raw:
        errors.append(f'{prefix}: expected 不能出现在用例顶层，只能作为 steps[i] 子字段。详见 {CONVENTIONS_DOC}')
    if 'tags' in raw:
        errors.append(f'{prefix}: tags 不能由 AI 写入用例（标签由脚本/后端统一赋值）。详见 {CONVENTIONS_DOC}')

    # 未知字段（拼写错误）
    unknown = set(raw.keys()) - _ALLOWED_CASE_FIELDS - {'name', 'prerequisite', 'expected', 'tags'}
    if unknown:
        errors.append(f'{prefix}: 未知字段 {sorted(unknown)}（可能拼写错误）。允许字段：{sorted(_ALLOWED_CASE_FIELDS)}')

    # 必填字段
    title = raw.get('title')
    if not isinstance(title, str) or not title.strip():
        errors.append(f'{prefix}: title 必填且非空字符串')
    elif len(title) > MAX_CASE_NAME_LENGTH:
        errors.append(f'{prefix}: title 长度 {len(title)} 超过上限 {MAX_CASE_NAME_LENGTH}')

    priority = raw.get('priority')
    if priority not in VALID_PRIORITIES:
        errors.append(f'{prefix}: priority 必须是 {sorted(VALID_PRIORITIES)} 之一，收到 {priority!r}')

    precond = raw.get('preconditions')
    if precond is None:
        errors.append(f'{prefix}: preconditions 必填（字符串数组，可空数组）')
    elif not isinstance(precond, list):
        errors.append(f'{prefix}: preconditions 必须是字符串数组，收到 {type(precond).__name__}')
    elif any(not isinstance(p, str) for p in precond):
        errors.append(f'{prefix}: preconditions 数组元素必须全是字符串')

    # steps 校验
    steps = raw.get('steps')
    if not isinstance(steps, list) or not steps:
        errors.append(f'{prefix}: steps 必填且至少 1 步')
    elif isinstance(steps[0], (str, bytes)):
        errors.append(
            f'{prefix}: steps 必须是 [{{action, expected}}] 配对对象数组，'
            f'不接受字符串数组。详见 {CONVENTIONS_DOC}',
        )
    else:
        # 检测是否 MS 内部格式（{num, desc, result}）— 允许透传
        # 用 num/result 而非 desc 判定：desc 容易被 AI 当 action 的 typo 误写，
        # num/result 是 MS 特有，不会被误用为 action/expected
        is_ms_format = isinstance(steps[0], dict) and (
            'num' in steps[0] or 'result' in steps[0]
        )
        for si, step in enumerate(steps):
            sprefix = f'{prefix} steps[{si}]'
            if not isinstance(step, dict):
                errors.append(f'{sprefix}: 必须是对象，收到 {type(step).__name__}')
                continue
            if is_ms_format:
                step_unknown = set(step.keys()) - _ALLOWED_MS_STEP_FIELDS
                if step_unknown:
                    errors.append(f'{sprefix}: 未知字段 {sorted(step_unknown)}（MS 格式只允许 {sorted(_ALLOWED_MS_STEP_FIELDS)}）')
                if not isinstance(step.get('desc'), str) or not step.get('desc', '').strip():
                    errors.append(f'{sprefix}: desc 必填且非空字符串')
            else:
                step_unknown = set(step.keys()) - _ALLOWED_STEP_FIELDS
                if step_unknown:
                    errors.append(f'{sprefix}: 未知字段 {sorted(step_unknown)}（可能拼写错误，允许：{sorted(_ALLOWED_STEP_FIELDS)}）')
                if not isinstance(step.get('action'), str) or not step.get('action', '').strip():
                    errors.append(f'{sprefix}: action 必填且非空字符串')
                expected = step.get('expected', '')
                if expected is not None and not isinstance(expected, str):
                    errors.append(f'{sprefix}: expected 必须是字符串（可为空字符串）')

    return errors


def _convert_case(raw: dict, *, tags: list[str] | None = None) -> dict:
    """将 schema 校验通过的用例转为 MS API 格式。

    输入只接受两种格式（AI 写入的旧格式已被 _validate_case_schema 拦截）：
    - 标准配对格式：steps[{action, expected}]
    - MS 内部格式（回流）：steps[{num, desc, result}]

    tags 由调用方按工作流类型指定（变更分析 'AI 变更分析' / 用例评审 'AI 用例评审'），
    AI 输出中的 tags 字段已被 _validate_case_schema 拦截。
    """
    steps_raw = raw['steps']
    if isinstance(steps_raw[0], dict) and 'desc' in steps_raw[0]:
        ms_steps = [
            {'num': s.get('num', i + 1),
             'desc': _sanitize_quotes(s.get('desc', '')),
             'result': _sanitize_quotes(s.get('result', ''))}
            for i, s in enumerate(steps_raw)
        ]
    else:
        ms_steps = [
            {'num': i + 1,
             'desc': _sanitize_quotes(s['action']),
             'result': _sanitize_quotes(s.get('expected', ''))}
            for i, s in enumerate(steps_raw)
        ]

    precond_list = raw.get('preconditions') or []
    precond = '\n'.join(precond_list)

    name = _sanitize_title(raw['title']).strip()
    if len(name) > MAX_CASE_NAME_LENGTH:
        name = name[:MAX_CASE_NAME_LENGTH] + '…'

    return {
        'name': name,
        'priority': raw['priority'],
        'prerequisite': _sanitize_quotes(precond),
        'steps': ms_steps,
        'tags': tags or ['AI 用例生成'],
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
        parts = ['未分类']
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
    # _get_modules 内部走 _request，失败已经走 _fail；不需要额外 try/except
    modules = _get_modules()
    count = sum(1 for _ in _iter_all_nodes(modules))
    print(json.dumps({
        'status': 'ok',
        'base_url': _cfg('MS_BASE_URL'),
        'project_id': _cfg('MS_PROJECT_ID'),
        'module_count': count,
    }, ensure_ascii=False, indent=2))


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


def cmd_import_cases(parent_module_id: str, cases_file: str,
                     requirement_name: str = '', tags: list[str] | None = None,
                     mapping_out: str | None = None):
    """按 module 字段分组导入用例，可选按需求名创建父模块；落盘 v2 ms_case_mapping.json。

    tags: 用例标签列表，默认 ['AI 用例生成']。
          变更分析使用 ['AI 变更分析']，用例评审使用 ['AI 用例评审']。
    mapping_out: v2 mapping 文件落盘路径，默认 <cases_file 同目录>/ms_case_mapping.json
    """
    if not parent_module_id:
        parent_module_id = _cfg('MS_DEFAULT_NODE_ID')

    # 如果指定了需求名，先创建需求级父模块，子模块挂在其下
    modules_created = 0
    if requirement_name:
        req_module = _ensure_module(parent_module_id, requirement_name)
        parent_module_id = req_module['id']
        if req_module.get('is_new'):
            modules_created += 1

    cases_path = Path(cases_file)
    with open(cases_path, 'rb') as f:
        cases_bytes = f.read()
    cases_sha = hashlib.sha256(cases_bytes).hexdigest()
    raw_cases = json.loads(cases_bytes.decode('utf-8'))

    # 严格契约：顶层必须是 list
    if not isinstance(raw_cases, list):
        detail = (
            f"收到 dict（含键 {list(raw_cases.keys())[:5]}）。禁止用 {{cases:[...]}} 或 {{modules:[...]}} 包裹"
            if isinstance(raw_cases, dict)
            else f"收到 {type(raw_cases).__name__}"
        )
        _fail(ERR_VALIDATION, f"用例文件顶层必须是 JSON 数组：{detail}",
              exit_code=2, hint=CONVENTIONS_DOC, file=cases_file)

    if not raw_cases:
        _fail(ERR_VALIDATION, "用例数组为空，至少需要 1 条用例",
              exit_code=2, file=cases_file)

    # 严格 schema 校验 — 失败即报错退出，让 AI 修正后重试
    all_errors: list[str] = []
    for idx, raw in enumerate(raw_cases):
        all_errors.extend(_validate_case_schema(raw, idx))
    if all_errors:
        _fail(ERR_VALIDATION,
              f"用例 schema 校验失败（{len(all_errors)} 处）",
              exit_code=2, hint=CONVENTIONS_DOC,
              errors=all_errors[:30],
              total_errors=len(all_errors))

    # 转换并按 module 分组；保留 (raw, converted) 配对以便后续 mapping 写 case_id
    # by_module: module_name → list of (raw_case, converted_case)
    by_module: dict[str, list[tuple[dict, dict]]] = {}
    for raw in raw_cases:
        converted = _convert_case(raw, tags=tags)
        module_name = raw.get('module', '未分类')
        by_module.setdefault(module_name, []).append((raw, converted))

    # 严格重名校验：同 module 内 (sanitized title) 出现 ≥2 条 → fail，
    # 让 case 生成阶段消歧（加序号或限定词）。不再走 _dedup_names 的静默 _2 后缀。
    duplicates = []
    for module_name, pairs in by_module.items():
        seen: dict[str, int] = {}
        for raw, conv in pairs:
            t = conv['name']  # 已经 _sanitize_title 过
            seen[t] = seen.get(t, 0) + 1
        for title, n in seen.items():
            if n > 1:
                duplicates.append({'module': module_name, 'title': title, 'count': n})
    if duplicates:
        _fail(ERR_VALIDATION,
              f"同模块内用例重名（{len(duplicates)} 组）；请在用例生成阶段消歧（加序号或限定词）",
              exit_code=2, duplicates=duplicates)

    # 逐模块创建子模块（顺序，避免并发创建重复模块）
    module_meta: dict[str, tuple[str, str]] = {}  # module_name → (module_id, module_path)
    for module_name in by_module:
        module_info, created = _ensure_module_path(parent_module_id, module_name)
        module_id = module_info['id']
        module_path = _get_module_path(module_id)
        module_meta[module_name] = (module_id, module_path)
        modules_created += created

    # 并发导入用例
    # 单条失败：HelperError（API/网络）会被 except 捕获 → 记 failed_details；
    # 整体不中断，让批次跑完。
    total_imported = 0
    total_failed = 0
    failed_details: list[dict] = []
    mapping_entries: list[dict] = []

    def _import_one(module_name: str, raw_case: dict, case_data: dict) -> dict | None:
        module_id, module_path = module_meta[module_name]
        case_id = raw_case.get('case_id') or case_data['name']
        try:
            result = _add_case(module_id, case_data, module_path=module_path)
            ms_id = ''
            if isinstance(result, dict):
                ms_id = str(result.get('id', ''))
            elif result is not None:
                ms_id = str(result)
            return {
                'case_id': case_id,
                'ms_id': ms_id,
                'title': case_data['name'],
                'module': module_name,
                'module_path': module_path,
                'import_status': 'created',
            }
        except HelperError as e:
            failed_details.append({
                'case_id': case_id, 'title': case_data['name'],
                'error_type': e.error_type, 'message': e.message,
            })
            return None
        except Exception as e:
            failed_details.append({
                'case_id': case_id, 'title': case_data['name'],
                'error_type': 'unexpected', 'message': str(e),
            })
            return None

    tasks = [(mn, raw, conv) for mn, pairs in by_module.items() for raw, conv in pairs]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_import_one, mn, raw, conv): (mn, raw, conv)
                   for mn, raw, conv in tasks}
        for future in as_completed(futures):
            result = future.result()
            if result:
                mapping_entries.append(result)
                total_imported += 1
            else:
                total_failed += 1

    # 落盘 v2 mapping 文件
    if mapping_out is None:
        mapping_out = str(cases_path.parent / 'ms_case_mapping.json')

    mapping_doc = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source_cases_file': {
            'path': str(cases_path.resolve()),
            'sha256': cases_sha,
        },
        'ms_project_id': _cfg('MS_PROJECT_ID'),
        'entries': mapping_entries,
    }
    Path(mapping_out).parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_out, 'w', encoding='utf-8') as f:
        json.dump(mapping_doc, f, ensure_ascii=False, indent=2)

    report = {
        'imported': total_imported,
        'failed': total_failed,
        'modules_created': modules_created,
        'mapping_path': str(Path(mapping_out).resolve()),
        'failed_details': failed_details,
        'metersphere_url': (
            f"{_cfg('MS_BASE_URL')}/#/track/case/all/{_cfg('MS_PROJECT_ID')}"
            f"?moduleId={parent_module_id}"
        ),
    }

    # 同时落盘 ms_import_report.json（P12 命名冲突防御：与 writeback 的 ms_sync_report.json 永不撞名）
    import_report_path = str(cases_path.parent / 'ms_import_report.json')
    import_report_doc = {
        'ran_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source_cases_file': {
            'path': str(cases_path.resolve()),
            'sha256': cases_sha,
        },
        'parent_module_id': parent_module_id,
        'requirement_name': requirement_name,
        **report,
    }
    with open(import_report_path, 'w', encoding='utf-8') as f:
        json.dump(import_report_doc, f, ensure_ascii=False, indent=2)
    report['import_report_path'] = import_report_path

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
        _fail(ERR_VALIDATION, "no case IDs provided", exit_code=2)
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
        _fail(ERR_VALIDATION,
              f"status must be one of: {sorted(valid)} (got {status!r})",
              exit_code=2)
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
    failed_details: list[dict] = []

    def _do_update(item):
        pcid = item.get('plan_case_id', '')
        try:
            _update_case_result(pcid, item.get('status', ''),
                                item.get('actual_result', ''), item.get('comment', ''))
            return (True, pcid, None)
        except SystemExit:
            raise
        except Exception as e:
            return (False, pcid, str(e))

    with ThreadPoolExecutor(max_workers=5) as executor:
        for ok, pcid, err in executor.map(_do_update, updates):
            if ok:
                success += 1
            else:
                failed += 1
                failed_details.append({'plan_case_id': pcid, 'error': err})

    print(json.dumps({
        'plan_id': plan_id,
        'total': len(updates),
        'success': success,
        'failed': failed,
        'failed_details': failed_details,
    }, ensure_ascii=False, indent=2))


# ==================== forward_verification 校验（P7） ====================

import hashlib  # noqa: E402  — 仅在 validate-fv / mapping 校验等命令路径用，集中放这里
from datetime import datetime, timezone  # noqa: E402

_DEFAULT_FV_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / '_shared' / 'schemas' / 'forward_verification.schema.json'
)


def _load_fv_schema(schema_path: str | None) -> dict:
    path = Path(schema_path) if schema_path else _DEFAULT_FV_SCHEMA_PATH
    if not path.exists():
        _fail(ERR_PRECONDITION,
              f"fv schema 文件不存在: {path}",
              hint='检查 plugins/test/skills/_shared/schemas/forward_verification.schema.json 是否存在',
              schema_path=str(path))
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _validate_code_location(loc: str, repo_root: Path) -> str | None:
    """校验 evidence.code_location 指向的文件存在且行号合法。返回错误消息（None 表示通过）。"""
    # 格式 file:line 或 file:start-end（schema 已用 pattern 校验过基本形态）
    if ':' not in loc:
        return f'格式错误（缺 :line）: {loc}'
    file_part, line_part = loc.rsplit(':', 1)
    file_path = repo_root / file_part
    if not file_path.exists():
        return f'文件不存在: {file_part}'
    try:
        if '-' in line_part:
            start, end = line_part.split('-', 1)
            start_n, end_n = int(start), int(end)
        else:
            start_n = end_n = int(line_part)
    except ValueError:
        return f'行号解析失败: {line_part}'
    try:
        with open(file_path, 'rb') as f:
            line_count = sum(1 for _ in f)
    except OSError as e:
        return f'读取文件失败: {file_part}: {e}'
    if start_n < 1 or end_n < start_n or end_n > line_count:
        return f'行号 {line_part} 越界（文件共 {line_count} 行）: {file_part}'
    return None


def _validate_fv_file(fv_path: Path, *, schema_path: str | None = None,
                       repo_root: str | None = None) -> list[dict]:
    """内部校验函数：返回合法 fv 数据；失败 → 抛 HelperError。

    抽出这一层是为了让 cmd_writeback_from_fv 能在 dry-run/真实跑前复用同一套校验，
    不需要走 CLI 的 print 出口。
    """
    if not fv_path.exists():
        _fail(ERR_PRECONDITION, f"fv 文件不存在: {fv_path}",
              hint='请确认 requirement-traceability 已产出 forward_verification.json')
    try:
        with open(fv_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        _fail(ERR_VALIDATION, f"fv 文件不是合法 JSON: {e}", exit_code=2,
              file=str(fv_path))

    schema = _load_fv_schema(schema_path)

    try:
        import jsonschema  # type: ignore
    except ImportError:
        _fail(ERR_DEPENDENCY_MISSING,
              "需要 jsonschema 库。请执行: pip install jsonschema")

    errors: list[dict] = []
    validator = jsonschema.Draft7Validator(schema)
    for err in validator.iter_errors(data):
        errors.append({
            'path': '$' + ''.join(f'[{p}]' if isinstance(p, int) else f'.{p}' for p in err.absolute_path),
            'message': err.message,
            'schema_path': '/'.join(str(p) for p in err.absolute_schema_path),
        })

    # boundary 校验：code_location 文件存在 + 行号合法。
    # schema 没炸的情况下才查；schema 炸了优先报 schema 错。
    used_repo_root: Path | None = None
    if not errors and isinstance(data, list):
        if repo_root:
            used_repo_root = Path(repo_root).resolve()
        else:
            # 从 fv 文件向上找 .git；找不到则兜底用 fv 同目录
            cur = fv_path.resolve().parent
            while cur != cur.parent and not (cur / '.git').exists():
                cur = cur.parent
            used_repo_root = cur if (cur / '.git').exists() else fv_path.resolve().parent
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                continue
            evidence = entry.get('evidence') or {}
            for j, loc in enumerate(evidence.get('code_location') or []):
                msg = _validate_code_location(loc, used_repo_root)
                if msg:
                    errors.append({
                        'path': f'$[{i}].evidence.code_location[{j}]',
                        'message': msg,
                        'schema_path': 'boundary/code_location_exists',
                    })

    if errors:
        extra = {'errors': errors[:30], 'total_errors': len(errors), 'file': str(fv_path)}
        if used_repo_root is not None:
            extra['repo_root'] = str(used_repo_root)
        _fail(ERR_VALIDATION,
              f"fv schema 校验失败（{len(errors)} 处）",
              exit_code=2, **extra)

    return data if isinstance(data, list) else []


def cmd_validate_fv(fv_path: str, *, schema_path: str | None = None,
                    repo_root: str | None = None) -> None:
    """按 schema 校验 forward_verification.json。CLI 出口。"""
    data = _validate_fv_file(Path(fv_path), schema_path=schema_path, repo_root=repo_root)
    print(json.dumps({
        'valid': True,
        'count': len(data),
        'file': str(fv_path),
    }, ensure_ascii=False, indent=2))


# ==================== mapping / lookup / refresh / writeback（Wave 2） ====================

def _load_mapping(mapping_path: str | None, *, fallback_dir: Path | None = None) -> tuple[Path, dict]:
    """加载 mapping 文件。mapping_path 不传时按 fallback_dir/ms_case_mapping.json 找。

    返回 (resolved_path, mapping_doc)；不存在或非法时抛 HelperError。
    """
    if mapping_path:
        path = Path(mapping_path)
    elif fallback_dir is not None:
        path = fallback_dir / 'ms_case_mapping.json'
    else:
        path = Path.cwd() / 'ms_case_mapping.json'

    if not path.exists():
        _fail(ERR_NOT_FOUND, f"mapping 文件不存在: {path}",
              hint='先跑 metersphere-sync mode=sync 生成 ms_case_mapping.json',
              mapping_path=str(path))
    try:
        with open(path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        _fail(ERR_VALIDATION, f"mapping 文件不是合法 JSON: {e}",
              exit_code=2, mapping_path=str(path))

    if not isinstance(doc, dict) or 'entries' not in doc:
        _fail(ERR_VALIDATION,
              f"mapping 文件格式不是 v2（应有顶层 entries 数组）: {path}",
              exit_code=2, mapping_path=str(path),
              hint='重跑 metersphere-sync mode=sync 让 import-cases 生成 v2 格式')
    return path, doc


def _check_mapping_freshness(mapping_doc: dict, cases_file: Path) -> None:
    """校验 mapping.source_cases_file.sha256 与当前 cases 文件 sha 一致。不一致 → fail。"""
    src = mapping_doc.get('source_cases_file') or {}
    expected_sha = src.get('sha256')
    if not expected_sha:
        return  # 老 mapping 没 sha 字段，跳过；refresh-mapping 会引导用户升级
    if not cases_file.exists():
        _fail(ERR_NOT_FOUND, f"cases 文件不存在: {cases_file}",
              cases_path=str(cases_file))
    with open(cases_file, 'rb') as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    if actual_sha != expected_sha:
        _fail(ERR_STALE_MAPPING,
              "mapping.source_cases_file.sha256 与当前 cases 文件不一致",
              hint='跑 refresh-mapping --diff-only 查差异，再 --apply 修复',
              expected_sha=expected_sha, actual_sha=actual_sha,
              cases_path=str(cases_file))


def _list_all_plan_cases(plan_id: str) -> list[dict]:
    """分页拉全 plan 下所有 case。"""
    out: list[dict] = []
    page = 1
    while True:
        result = _list_plan_cases(plan_id, page=page, page_size=100)
        cases = result.get('listObject', []) or []
        out.extend(cases)
        total = result.get('itemCount', 0)
        if len(out) >= total or not cases:
            break
        page += 1
    return out


def cmd_lookup_plan_case(*, plan_id: str, case_id: str,
                          mapping_path: str | None = None) -> None:
    """case_id → ms_id (查 mapping) → plan_case_id (查 MS plan) 三级查找。"""
    _, mapping_doc = _load_mapping(mapping_path)

    entries = mapping_doc.get('entries') or []
    entry = next((e for e in entries if e.get('case_id') == case_id), None)
    if entry is None:
        _fail(ERR_NOT_FOUND, f"case_id {case_id} not in mapping",
              hint='跑 metersphere_helper.py refresh-mapping --diff-only 查差异',
              mapping_path=mapping_path or 'cwd/ms_case_mapping.json',
              case_id=case_id)

    ms_id = entry.get('ms_id')
    if not ms_id:
        _fail(ERR_VALIDATION, f"mapping entry for {case_id} 缺 ms_id",
              exit_code=2, entry=entry)

    all_pc = _list_all_plan_cases(plan_id)
    # MS API: case 级 UUID 在 caseId 字段；plan_case 行 ID 在 id 字段
    pc = next((p for p in all_pc if p.get('caseId') == ms_id), None)
    if pc is None:
        _fail(ERR_NOT_FOUND,
              f"ms_id {ms_id} not in plan {plan_id}（case 可能未 add 到 plan）",
              ms_id=ms_id, plan_id=plan_id, case_id=case_id)

    print(json.dumps({
        'case_id': case_id,
        'ms_id': ms_id,
        'plan_case_id': pc.get('id'),
        'match_method': 'mapping',
        'title': entry.get('title', ''),
    }, ensure_ascii=False, indent=2))


def cmd_refresh_mapping(*, mapping_path: str, cases_path: str,
                         apply_changes: bool = False) -> None:
    """比对 mapping 与 cases；apply 时清理 stale 条目。

    extra_in_ms（MS 端独立加的 case）需要扫 module，本版本不查，永远输出空数组——
    MS 端独立加的 case 不在 traceability 体系内，由人工域处理。
    """
    map_path = Path(mapping_path)
    cases_file = Path(cases_path)
    if not map_path.exists():
        _fail(ERR_NOT_FOUND, f"mapping 文件不存在: {mapping_path}")
    if not cases_file.exists():
        _fail(ERR_NOT_FOUND, f"cases 文件不存在: {cases_path}")

    with open(map_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    with open(cases_file, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        _fail(ERR_VALIDATION, f"cases 文件顶层不是数组: {cases_path}", exit_code=2)
    if not isinstance(mapping, dict) or 'entries' not in mapping:
        _fail(ERR_VALIDATION, f"mapping 不是 v2 格式: {mapping_path}",
              exit_code=2, hint='重跑 import-cases 生成 v2')

    case_ids_in_cases = {
        (c.get('case_id') or c.get('title')): c
        for c in cases if isinstance(c, dict)
    }
    entries_by_id = {e['case_id']: e for e in mapping.get('entries', [])
                     if isinstance(e, dict) and 'case_id' in e}

    missing = [
        {'case_id': cid, 'title': c.get('title', ''), 'module': c.get('module', '')}
        for cid, c in case_ids_in_cases.items()
        if cid not in entries_by_id
    ]
    stale = [
        {'case_id': cid, 'ms_id': e.get('ms_id'), 'title': e.get('title', '')}
        for cid, e in entries_by_id.items()
        if cid not in case_ids_in_cases
    ]

    diff = {
        'mapping_path': str(map_path.resolve()),
        'cases_path': str(cases_file.resolve()),
        'missing_in_mapping': missing,
        'stale_in_mapping': stale,
        'extra_in_ms': [],
        'apply_done': False,
    }

    if apply_changes and (stale or missing):
        # apply：本版本只清 stale。missing 需要重 import 模块上下文，让用户主动跑 sync。
        if stale:
            stale_ids = {s['case_id'] for s in stale}
            mapping['entries'] = [e for e in mapping.get('entries', [])
                                  if e.get('case_id') not in stale_ids]
            mapping['generated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            # 同步更新 sha 防再次报 stale
            with open(cases_file, 'rb') as f:
                new_sha = hashlib.sha256(f.read()).hexdigest()
            mapping.setdefault('source_cases_file', {})['sha256'] = new_sha
            mapping['source_cases_file']['path'] = str(cases_file.resolve())
            with open(map_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            diff['apply_done'] = True
        if missing:
            diff['missing_action'] = (
                '请重跑 metersphere-sync mode=sync 来 import 这些 case'
            )

    print(json.dumps(diff, ensure_ascii=False, indent=2))

    # 非空 diff → exit 1（让调用方知道有事）
    if missing or stale:
        sys.exit(1)


def cmd_rebuild_mapping(*, plan_id: str, cases_path: str,
                         mapping_out: str | None = None) -> None:
    """从 MS plan 反向重建 ms_case_mapping.json（P11）。

    场景：切换 plan / 重 import 后，旧 mapping 的 ms_id 已经过期，refresh-mapping 救不了。
    本命令拉 plan 全部 plan_cases，按 plan_case.name == cases.title 匹配本地 cases，
    重建一份正确的 mapping 文件。

    title 撞名时不能拍脑袋——直接报 ambiguous 让用户消歧。
    """
    cases_file = Path(cases_path)
    if not cases_file.exists():
        _fail(ERR_NOT_FOUND, f"cases 文件不存在: {cases_path}",
              cases_path=str(cases_path))
    with open(cases_file, 'rb') as f:
        cases_bytes = f.read()
    cases_sha = hashlib.sha256(cases_bytes).hexdigest()
    cases = json.loads(cases_bytes.decode('utf-8'))
    if not isinstance(cases, list):
        _fail(ERR_VALIDATION, f"cases 文件顶层不是数组: {cases_path}",
              exit_code=2, cases_path=str(cases_path))

    # 本地 cases：title → case 字典；同时检查同模块重名（与 import-cases 一致）
    local_by_title: dict[str, dict] = {}
    title_collisions: list[dict] = []
    for c in cases:
        if not isinstance(c, dict):
            continue
        title = c.get('title', '')
        if not title:
            continue
        sanitized = _sanitize_title(title)
        if sanitized in local_by_title:
            existing = local_by_title[sanitized]
            title_collisions.append({
                'title': sanitized,
                'case_ids': [existing.get('case_id'), c.get('case_id')],
                'modules': [existing.get('module'), c.get('module')],
            })
            continue  # 后来的不进字典；ambiguous 集体报告
        local_by_title[sanitized] = c

    # 拉 plan 全部 plan_cases
    all_pc = _list_all_plan_cases(plan_id)

    matched: list[dict] = []
    unmatched_in_plan: list[dict] = []
    seen_titles_in_plan: dict[str, list[dict]] = {}

    for pc in all_pc:
        pc_name = pc.get('name', '')
        sanitized = _sanitize_title(pc_name)
        seen_titles_in_plan.setdefault(sanitized, []).append(pc)

    ambiguous_titles: list[dict] = list(title_collisions)
    for sanitized, pc_group in seen_titles_in_plan.items():
        if len(pc_group) > 1:
            # plan 里 title 撞名 → ambiguous
            ambiguous_titles.append({
                'title': sanitized,
                'source': 'plan',
                'plan_case_ids': [pc.get('id') for pc in pc_group],
                'ms_ids': [pc.get('caseId') for pc in pc_group],
            })
            continue
        pc = pc_group[0]
        local = local_by_title.get(sanitized)
        if local is None:
            unmatched_in_plan.append({
                'plan_case_id': pc.get('id'),
                'ms_id': pc.get('caseId'),
                'name': pc_name,
            })
            continue
        matched.append({
            'case_id': local.get('case_id') or local.get('title'),
            'ms_id': pc.get('caseId'),
            'title': sanitized,
            'module': local.get('module', ''),
            'module_path': pc.get('nodePath', ''),
            'import_status': 'reused',  # 反向重建一律标记 reused
        })

    matched_titles = {e['title'] for e in matched}
    unmatched_local = [
        {
            'case_id': c.get('case_id') or c.get('title'),
            'title': _sanitize_title(c.get('title', '')),
            'module': c.get('module', ''),
        }
        for c in cases
        if isinstance(c, dict)
        and _sanitize_title(c.get('title', '')) not in matched_titles
        and _sanitize_title(c.get('title', '')) not in {a['title'] for a in ambiguous_titles}
    ]

    # 落盘 mapping
    if mapping_out is None:
        mapping_out = str(cases_file.parent / 'ms_case_mapping.json')

    mapping_doc = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source_cases_file': {
            'path': str(cases_file.resolve()),
            'sha256': cases_sha,
        },
        'ms_project_id': _cfg('MS_PROJECT_ID'),
        'rebuilt_from_plan': plan_id,
        'entries': matched,
    }

    # ambiguous 时不落盘，仅报告——免得用户拿到半残的 mapping 用错
    if not ambiguous_titles:
        Path(mapping_out).parent.mkdir(parents=True, exist_ok=True)
        with open(mapping_out, 'w', encoding='utf-8') as f:
            json.dump(mapping_doc, f, ensure_ascii=False, indent=2)
        report_path = str(Path(mapping_out).resolve())
    else:
        report_path = None

    report = {
        'mapping_path': report_path,
        'plan_id': plan_id,
        'total_in_plan': len(all_pc),
        'matched': len(matched),
        'unmatched_in_plan': unmatched_in_plan,
        'unmatched_local': unmatched_local,
        'ambiguous_titles': ambiguous_titles,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if ambiguous_titles:
        # ambiguous 是数据问题，需要人工介入；不落盘 mapping，exit 1 提示调用方
        sys.exit(1)
    if unmatched_local:
        # 本地有但 plan 里没找到 → 提示但不阻塞
        sys.exit(1)


def _compose_writeback_comment(entry: dict, target: str, ext_dep_types: list[str],
                                confidence) -> str:
    """按 P6 状态映射拼 comment（人话，不塞 JSON）。"""
    conf_part = f"conf={confidence}" if confidence is not None else "conf=null"
    if entry.get('result') == 'pass':
        if ext_dep_types:
            return f"AI 静态验证通过 ({conf_part})，待人工验证: {', '.join(ext_dep_types)}"
        return f"AI 静态验证通过 ({conf_part})"
    if entry.get('result') == 'fail':
        evidence = entry.get('evidence') or {}
        first_loc = (evidence.get('code_location') or [''])[0]
        actual = entry.get('actual', '') or evidence.get('verification_logic', '')
        actual_brief = actual[:120] + ('…' if len(actual) > 120 else '')
        return f"AI 判定不通过 ({conf_part}) — evidence: {first_loc} — 失败原因: {actual_brief}"
    if entry.get('result') == 'inconclusive':
        reason = entry.get('inconclusive_reason') or 'unknown'
        return f"AI 无法判定 — 原因: {reason}"
    return f"AI 判定: {entry.get('result')}"


def _compute_target_status(entry: dict) -> tuple[str | None, list[str]]:
    """P6 状态映射 → (MS target status, ext_dep_types)。

    ext_dep_types 用于 comment 拼接和 caveats 报告分组。
    返回 (None, []) 表示 result 未识别（调用方记 failed）。
    """
    result = entry.get('result')
    ext_dep_types = ((entry.get('external_dependencies') or {}).get('types') or [])
    if result == 'pass':
        return ('Prepare' if ext_dep_types else 'Pass'), ext_dep_types
    if result == 'fail':
        return 'Failure', ext_dep_types
    if result == 'inconclusive':
        return 'Prepare', ext_dep_types
    return None, ext_dep_types


def _write_caveats_reports(fv: list[dict], out_dir: Path) -> dict:
    """从 fv 聚合生成 pass_with_caveats.md + pending_external_validation.md（P6 + P8）。

    返回路径字典。
    """
    pass_with_caveats: list[dict] = []
    pending_by_dep: dict[str, list[dict]] = {}
    for entry in fv:
        if entry.get('result') != 'pass':
            continue
        ext = (entry.get('external_dependencies') or {}).get('types') or []
        if not ext:
            continue
        item = {
            'case_id': entry.get('case_id'),
            'requirement_id': entry.get('requirement_id'),
            'requirement_name': entry.get('requirement_name', ''),
            'confidence': entry.get('confidence'),
            'types': ext,
            'notes': (entry.get('external_dependencies') or {}).get('notes', ''),
        }
        pass_with_caveats.append(item)
        for t in ext:
            pending_by_dep.setdefault(t, []).append(item)

    out_dir.mkdir(parents=True, exist_ok=True)

    pwc_path = out_dir / 'pass_with_caveats.md'
    with open(pwc_path, 'w', encoding='utf-8') as f:
        f.write('# Pass with Caveats（AI 静态通过但需人工回归）\n\n')
        if not pass_with_caveats:
            f.write('（本次没有需要标注 caveat 的 pass）\n')
        else:
            f.write(f'共 {len(pass_with_caveats)} 条。\n\n')
            f.write('| case_id | requirement | conf | types | notes |\n')
            f.write('| --- | --- | --- | --- | --- |\n')
            for it in pass_with_caveats:
                f.write(f'| {it["case_id"]} | {it["requirement_id"]} {it["requirement_name"]} '
                        f'| {it["confidence"]} | {", ".join(it["types"])} | {it["notes"]} |\n')

    pev_path = out_dir / 'pending_external_validation.md'
    with open(pev_path, 'w', encoding='utf-8') as f:
        f.write('# Pending External Validation（按依赖类型分组）\n\n')
        if not pending_by_dep:
            f.write('（本次没有待外部验证的 case）\n')
        else:
            for dep_type in sorted(pending_by_dep):
                items = pending_by_dep[dep_type]
                f.write(f'## {dep_type}（{len(items)} 条）\n\n')
                f.write('| case_id | requirement | conf | notes |\n')
                f.write('| --- | --- | --- | --- |\n')
                for it in items:
                    f.write(f'| {it["case_id"]} | {it["requirement_id"]} {it["requirement_name"]} '
                            f'| {it["confidence"]} | {it["notes"]} |\n')
                f.write('\n')

    return {
        'pass_with_caveats': str(pwc_path.resolve()),
        'pending_external_validation': str(pev_path.resolve()),
        'pass_with_caveats_count': len(pass_with_caveats),
        'pending_by_dep_count': {k: len(v) for k, v in pending_by_dep.items()},
    }


def cmd_writeback_from_fv(*, plan_id: str, fv_path: str,
                           mapping_path: str | None = None,
                           report_path: str | None = None,
                           dry_run: bool = False) -> None:
    """端到端：fv → MS plan 状态回写。

    流程：
      1. validate fv（schema + boundary）
      2. list-plan-cases 一次拉全（幂等比对）
      3. for each fv：决定 target_status (P6) → lookup → 比对 → update（含 retry）
      4. 写 ms_sync_report.json + forward_verification.enriched.json
      5. 写 pass_with_caveats.md + pending_external_validation.md
      6. 任一条目失败 → exit 1，全成功 → exit 0
    """
    fv_file = Path(fv_path)
    if not fv_file.exists():
        _fail(ERR_NOT_FOUND, f"fv 文件不存在: {fv_path}",
              hint='先跑 requirement-traceability skill 生成 forward_verification.json')

    # 1. 校验 fv（schema + boundary）；失败抛 HelperError 直接走 main 出口
    fv = _validate_fv_file(fv_file)

    # mapping 加载（fv 同目录默认）
    _, mapping_doc = _load_mapping(mapping_path, fallback_dir=fv_file.parent)
    mapping_by_case_id = {e['case_id']: e for e in mapping_doc.get('entries', [])
                          if isinstance(e, dict) and 'case_id' in e}

    # 2. 拉 plan 全部 case（幂等比对用）
    all_pc = _list_all_plan_cases(plan_id)
    pc_by_ms_id = {pc.get('caseId'): pc for pc in all_pc}

    # 3. 处理每条 fv
    enriched_fv: list[dict] = []
    updated: list[dict] = []
    unchanged: list[dict] = []
    failed: list[dict] = []
    by_target_status = {'Pass': 0, 'Prepare': 0, 'Failure': 0}

    for entry in fv:
        case_id = entry.get('case_id')
        target, ext_dep_types = _compute_target_status(entry)
        new_entry = dict(entry)  # 后续会附 ms_id

        if target is None:
            failed.append({
                'case_id': case_id,
                'error_type': 'unknown_result',
                'message': f"unknown result: {entry.get('result')}",
            })
            enriched_fv.append(new_entry)
            continue

        # 找 ms_id（fv 内嵌优先）
        ms_id = entry.get('ms_id')
        if not ms_id:
            map_entry = mapping_by_case_id.get(case_id)
            if not map_entry:
                failed.append({
                    'case_id': case_id,
                    'error_type': 'mapping_miss',
                    'message': f"{case_id} not in mapping",
                })
                enriched_fv.append(new_entry)
                continue
            ms_id = map_entry.get('ms_id')

        # 查 plan_case_id
        pc = pc_by_ms_id.get(ms_id)
        if pc is None:
            failed.append({
                'case_id': case_id,
                'error_type': 'not_in_plan',
                'message': f"ms_id {ms_id} not in plan {plan_id}",
            })
            enriched_fv.append(new_entry)
            continue
        plan_case_id = pc.get('id')
        current_status = pc.get('status')

        # 幂等：当前状态 == target → skip
        if current_status == target:
            unchanged.append({
                'case_id': case_id, 'status': target,
                'plan_case_id': plan_case_id, 'ms_id': ms_id,
            })
            new_entry['ms_id'] = ms_id
            enriched_fv.append(new_entry)
            by_target_status[target] += 1
            continue

        # 拼 comment
        comment = _compose_writeback_comment(entry, target, ext_dep_types, entry.get('confidence'))

        if dry_run:
            updated.append({
                'case_id': case_id, 'target': target,
                'from': current_status, 'plan_case_id': plan_case_id,
                'ms_id': ms_id, 'comment': comment, 'dry_run': True,
            })
            new_entry['ms_id'] = ms_id
            enriched_fv.append(new_entry)
            by_target_status[target] += 1
            continue

        # 真实 update：retriable 错误重试 1 次
        attempts = 0
        last_err: HelperError | None = None
        success = False
        while attempts < 2:
            try:
                _update_case_result(plan_case_id, target, '', comment)
                success = True
                break
            except HelperError as e:
                last_err = e
                if not e.retriable or attempts >= 1:
                    break
                time.sleep(1)
                attempts += 1
            except Exception as e:
                last_err = HelperError(ERR_API, f"{type(e).__name__}: {e}")
                break

        if success:
            updated.append({
                'case_id': case_id, 'target': target, 'from': current_status,
                'plan_case_id': plan_case_id, 'ms_id': ms_id,
            })
            new_entry['ms_id'] = ms_id
            enriched_fv.append(new_entry)
            by_target_status[target] += 1
        else:
            err_payload = last_err.to_payload() if last_err else {'message': 'unknown'}
            failed.append({
                'case_id': case_id,
                'error_type': err_payload.get('type', 'api_error'),
                'message': err_payload.get('message', ''),
                'retriable': err_payload.get('retriable', False),
                'plan_case_id': plan_case_id,
            })
            enriched_fv.append(new_entry)

    # 4. 报告 + enriched fv
    out_dir = fv_file.parent
    if report_path is None:
        report_path = str(out_dir / 'ms_sync_report.json')
    enriched_path = str(out_dir / 'forward_verification.enriched.json')

    summary = {
        'total': len(fv),
        'updated': len(updated),
        'unchanged': len(unchanged),
        'failed': len(failed),
        'by_target_status': by_target_status,
    }

    report = {
        'plan_id': plan_id,
        'fv_path': str(fv_file.resolve()),
        'ran_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'dry_run': dry_run,
        'summary': summary,
        'updated': updated,
        'unchanged': unchanged,
        'failed': failed,
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(enriched_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_fv, f, ensure_ascii=False, indent=2)

    # 5. caveats 报告（P6 + P8）
    caveats_paths = _write_caveats_reports(fv, out_dir)

    print(json.dumps({
        'report_path': str(Path(report_path).resolve()),
        'enriched_fv_path': str(Path(enriched_path).resolve()),
        'caveats': caveats_paths,
        'summary': summary,
    }, ensure_ascii=False, indent=2))

    # 任何失败 → exit 1
    if failed:
        sys.exit(1)


# ==================== CLI 入口 ====================

def _flag_value(args: list[str], flag: str, default: str | None = None) -> str | None:
    """从 args 中读取 --flag 后跟的值。flag 不存在返回 default；存在但缺值时清晰报错退出。"""
    if flag not in args:
        return default
    idx = args.index(flag)
    if idx + 1 >= len(args):
        _fail(ERR_VALIDATION, f"{flag} 缺少参数值", exit_code=2, flag=flag)
    return args[idx + 1]


def _flag_present(args: list[str], flag: str) -> bool:
    return flag in args


def _usage(text: str) -> None:
    _fail(ERR_VALIDATION, f"用法: {text}", exit_code=2)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        sys.exit(0 if len(sys.argv) >= 2 else 2)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == 'ping':
            cmd_ping()
        elif cmd == 'list-modules':
            parent = _flag_value(args, '--parent-id', '')
            cmd_list_modules(parent)
        elif cmd == 'ensure-module':
            if len(args) < 2:
                _usage("ensure-module <parent_id> <name>")
            cmd_ensure_module(args[0], args[1])
        elif cmd == 'import-cases':
            if len(args) < 2:
                _usage("import-cases <parent_module_id> <cases.json> "
                       "[--requirement <需求名>] [--tags 'AI 变更分析'] "
                       "[--mapping-out PATH]")
            req_name = _flag_value(args, '--requirement', '')
            tags_raw = _flag_value(args, '--tags')
            import_tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else None
            mapping_out = _flag_value(args, '--mapping-out')
            cmd_import_cases(args[0], args[1], requirement_name=req_name,
                             tags=import_tags, mapping_out=mapping_out)
        elif cmd == 'list-stages':
            cmd_list_stages()
        elif cmd == 'find-or-create-plan':
            if len(args) < 1:
                _usage("find-or-create-plan <plan_name> [--stage smoke]")
            stage = _flag_value(args, '--stage', 'smoke')
            if '--stage' in args:
                idx = args.index('--stage')
                args = args[:idx] + args[idx+2:]
            cmd_find_or_create_plan(args[0], stage)
        elif cmd == 'add-cases-to-plan':
            if len(args) < 3 or args[1] != '--case-ids':
                _usage("add-cases-to-plan <plan_id> --case-ids id1,id2,...")
            cmd_add_cases_to_plan(args[0], args[2])
        elif cmd == 'list-plan-cases':
            if len(args) < 1:
                _usage("list-plan-cases <plan_id>")
            cmd_list_plan_cases(args[0])
        elif cmd == 'update-case-result':
            if len(args) < 2:
                _usage("update-case-result <plan_case_id> <status> "
                       "[--actual-result TEXT] [--comment TEXT]")
            actual = _flag_value(args, '--actual-result', '')
            comment = _flag_value(args, '--comment', '')
            cmd_update_case_result(args[0], args[1], actual, comment)
        elif cmd == 'batch-update-results':
            if len(args) < 3 or args[1] != '--results-json':
                _usage("batch-update-results <plan_id> --results-json <file>")
            cmd_batch_update_results(args[0], args[2])
        elif cmd == 'validate-fv':
            if len(args) < 1:
                _usage("validate-fv <fv.json> [--schema-path PATH] [--repo-root PATH]")
            schema_path = _flag_value(args, '--schema-path')
            repo_root = _flag_value(args, '--repo-root')
            cmd_validate_fv(args[0], schema_path=schema_path, repo_root=repo_root)
        elif cmd == 'lookup-plan-case':
            if not (_flag_present(args, '--plan-id') and _flag_present(args, '--case-id')):
                _usage("lookup-plan-case --plan-id <id> --case-id <local_id> "
                       "[--mapping-path PATH]")
            cmd_lookup_plan_case(
                plan_id=_flag_value(args, '--plan-id'),
                case_id=_flag_value(args, '--case-id'),
                mapping_path=_flag_value(args, '--mapping-path'),
            )
        elif cmd == 'refresh-mapping':
            if not (_flag_present(args, '--mapping-path') and _flag_present(args, '--cases-path')):
                _usage("refresh-mapping --mapping-path PATH --cases-path final_cases.json "
                       "[--diff-only|--apply]")
            cmd_refresh_mapping(
                mapping_path=_flag_value(args, '--mapping-path'),
                cases_path=_flag_value(args, '--cases-path'),
                apply_changes=_flag_present(args, '--apply'),
            )
        elif cmd == 'rebuild-mapping':
            if not (_flag_present(args, '--plan-id') and _flag_present(args, '--cases-path')):
                _usage("rebuild-mapping --plan-id <id> --cases-path final_cases.json "
                       "[--mapping-out PATH]")
            cmd_rebuild_mapping(
                plan_id=_flag_value(args, '--plan-id'),
                cases_path=_flag_value(args, '--cases-path'),
                mapping_out=_flag_value(args, '--mapping-out'),
            )
        elif cmd == 'writeback-from-fv':
            if not (_flag_present(args, '--plan-id') and _flag_present(args, '--fv-path')):
                _usage("writeback-from-fv --plan-id <id> --fv-path <fv.json> "
                       "[--mapping-path PATH] [--report-path PATH] [--dry-run]")
            cmd_writeback_from_fv(
                plan_id=_flag_value(args, '--plan-id'),
                fv_path=_flag_value(args, '--fv-path'),
                mapping_path=_flag_value(args, '--mapping-path'),
                report_path=_flag_value(args, '--report-path'),
                dry_run=_flag_present(args, '--dry-run'),
            )
        else:
            _fail(ERR_VALIDATION, f"未知命令: {cmd}", exit_code=2,
                  hint="可用命令见脚本顶部 docstring")
    except HelperError as e:
        # 统一失败出口：所有 _fail 都走这里
        print(json.dumps(e.to_payload(), ensure_ascii=False), file=sys.stderr)
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        # 真兜底：未预见异常。记录类型方便排查。
        payload = {
            'type': ERR_API,
            'message': f"{type(e).__name__}: {e}",
            'retriable': False,
            'original_error': type(e).__name__,
        }
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
