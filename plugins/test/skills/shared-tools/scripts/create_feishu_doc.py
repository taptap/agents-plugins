#!/usr/bin/env python3
"""
飞书文档创建工具 — 供 AI Agent 在分析报告阶段使用

将 Markdown 内容创建为飞书云文档，支持自动移动到 Wiki 知识库。

子命令：
  create    从文件或 stdin 读取 Markdown 并创建飞书文档

用法:
    python3 create_feishu_doc.py create --title "报告标题" --file report.md
    python3 create_feishu_doc.py create --title "报告标题"          # 从 stdin 读取
    python3 create_feishu_doc.py create --title "标题" --no-wiki    # 不移动到 Wiki

环境变量:
    FEISHU_APP_ID           - 飞书应用 App ID（必需）
    FEISHU_APP_SECRET       - 飞书应用 App Secret（必需）
    FEISHU_BASE_URL         - 飞书 API 基础地址（默认 https://open.feishu.cn）
    FEISHU_WIKI_SPACE_ID    - Wiki 空间 ID（移动到 Wiki 时必需）
    FEISHU_WIKI_PARENT_TOKEN - Wiki 父节点 token（默认内置值）

输出:
    stdout: JSON 格式结果 {"url": "...", "title": "...", "wiki_url": "..."}
    stderr: 日志/进度信息
"""

import contextlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

# ==================== 配置 ====================

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn")

# Wiki 配置
FEISHU_WIKI_SPACE_ID = os.environ.get("FEISHU_WIKI_SPACE_ID", "")
FEISHU_WIKI_PARENT_TOKEN = os.environ.get("FEISHU_WIKI_PARENT_TOKEN", "")

# 飞书文档 URL 前缀
FEISHU_DOC_URL_PREFIX = os.environ.get(
    "FEISHU_DOC_URL_PREFIX", "https://xd.feishu.cn"
)

# Import Task 轮询参数
IMPORT_POLL_INTERVAL = 2  # 轮询间隔（秒）
IMPORT_POLL_MAX_RETRIES = 15  # 最多轮询次数（共 30 秒）

# HTTP 重试：仅重试瞬时可恢复的服务端/网络错误
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

# 飞书 Import Task API 不支持的 emoji → 文本替代映射
EMOJI_REPLACEMENTS = {
    '\u2705': '[OK]',       # ✅
    '\u26a0\ufe0f': '[!]',  # ⚠️
    '\u274c': '[X]',        # ❌
    '\U0001f41b': '[Bug]',  # 🐛
    '\U0001f4cb': '[Doc]',  # 📋
    '\U0001f680': '[Go]',   # 🚀
    '\U0001f4dd': '[Note]', # 📝
    '\U0001f50d': '[Find]', # 🔍
    '\U0001f527': '[Tool]', # 🔧
    '\U0001f4a1': '[Tip]',  # 💡
    '\U0001f4e6': '[Pkg]',  # 📦
    '\U0001f4ca': '[Chart]',  # 📊
    '\U0001f6a8': '[Alert]',  # 🚨
}

# tenant_access_token 模块级缓存
_token_cache = {"token": "", "expires_at": 0.0}


# ==================== 日志 ====================

def _log(msg: str):
    """输出日志到 stderr"""
    print(f"[feishu-doc] {msg}", file=sys.stderr)


def _error(msg: str):
    """输出错误到 stderr"""
    print(f"[feishu-doc][ERROR] {msg}", file=sys.stderr)


# ==================== HTTP 工具 ====================

def _urlopen_with_retry(req, *, timeout=30, max_retries=3):
    """urllib.request.urlopen 的重试包装，处理瞬时网络/服务端错误"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in RETRYABLE_HTTP_CODES and attempt < max_retries:
                delay = 2 ** (attempt - 1)
                _log(f"HTTP {e.code}(第{attempt}/{max_retries}次)，{delay}秒后重试")
                time.sleep(delay)
                last_error = e
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < max_retries:
                delay = 2 ** (attempt - 1)
                _log(f"网络错误(第{attempt}/{max_retries}次)，{delay}秒后重试: {e.reason}")
                time.sleep(delay)
                last_error = e
                continue
            raise
    raise last_error


def _api_post_json(url: str, token: str, payload: dict) -> dict:
    """
    发送 JSON POST 请求到飞书 API

    Args:
        url: 完整 API URL
        token: access_token
        payload: JSON body

    Returns:
        响应 JSON dict
    """
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with _urlopen_with_retry(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        with contextlib.suppress(Exception):
            error_body = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"HTTP Error {e.code}: {e.reason}\n  URL: {url}\n  Body: {error_body}"
        )
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络连接失败: {e.reason}\n  URL: {url}")


def _api_get(url: str, token: str) -> dict:
    """发送 GET 请求到飞书 API"""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with _urlopen_with_retry(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        with contextlib.suppress(Exception):
            error_body = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"HTTP Error {e.code}: {e.reason}\n  URL: {url}\n  Body: {error_body}"
        )
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络连接失败: {e.reason}\n  URL: {url}")


def _api_post_multipart(url: str, token: str, fields: dict, files: dict) -> dict:
    """
    发送 multipart/form-data POST 请求（纯 stdlib 实现）

    Args:
        url: 完整 API URL
        token: access_token
        fields: 普通表单字段 {name: value}
        files: 文件字段 {name: (filename, data_bytes, content_type)}

    Returns:
        响应 JSON dict
    """
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()

    # 写入普通字段
    for key, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        )
        buf.write(f"{value}\r\n".encode())

    # 写入文件字段
    for key, (filename, data, content_type) in files.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{key}"; '
            f'filename="{filename}"\r\n'.encode()
        )
        buf.write(f"Content-Type: {content_type}\r\n\r\n".encode())
        buf.write(data)
        buf.write(b"\r\n")

    # 结束标记
    buf.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=buf.getvalue(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with _urlopen_with_retry(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        with contextlib.suppress(Exception):
            error_body = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"HTTP Error {e.code}: {e.reason}\n  URL: {url}\n  Body: {error_body}"
        )
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络连接失败（文件上传）: {e.reason}\n  URL: {url}")


# ==================== 飞书 API 封装 ====================

def get_tenant_access_token() -> str:
    """
    获取飞书 tenant_access_token（带模块级缓存）

    Returns:
        access_token 字符串

    Raises:
        RuntimeError: 获取失败
    """
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        raise RuntimeError(
            "环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET 未配置"
        )

    url = f"{FEISHU_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with _urlopen_with_retry(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {data}")

    token = data["tenant_access_token"]
    expire = data.get("expire", 7200)
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + expire - 120
    _log("获取 tenant_access_token 成功")
    return token


def upload_markdown_file(token: str, title: str, markdown: str) -> str:
    """
    上传 Markdown 内容为临时文件，返回 file_token

    使用接口: POST /open-apis/drive/v1/medias/upload_all
    """
    file_name = f"{title}.md" if title else "report.md"
    file_bytes = markdown.encode("utf-8")
    file_size = len(file_bytes)

    _log(f"上传 Markdown 文件: {file_name} ({file_size} bytes)")

    url = f"{FEISHU_BASE_URL}/open-apis/drive/v1/medias/upload_all"
    data = _api_post_multipart(
        url,
        token,
        fields={
            "file_name": file_name,
            "parent_type": "explorer",
            "parent_node": "",
            "size": str(file_size),
        },
        files={
            "file": (file_name, file_bytes, "text/markdown"),
        },
    )

    if data.get("code") != 0:
        raise RuntimeError(f"上传 Markdown 文件失败: {data}")

    file_token = data.get("data", {}).get("file_token", "")
    if not file_token:
        raise RuntimeError(f"上传成功但未获取到 file_token: {data}")

    _log(f"上传成功: file_token={file_token}")
    return file_token


def create_import_task(token: str, file_token: str, title: str) -> str:
    """
    创建导入任务（md → docx），返回 ticket

    使用接口: POST /open-apis/drive/v1/import_tasks
    """
    _log("创建导入任务 (md → docx)...")

    url = f"{FEISHU_BASE_URL}/open-apis/drive/v1/import_tasks"
    data = _api_post_json(url, token, {
        "file_extension": "md",
        "file_token": file_token,
        "type": "docx",
        "file_name": title or "变更分析报告",
        "point": {
            "mount_type": 1,  # 1 = 个人云空间 (explorer)
            "mount_key": "",  # 空字符串 = 根目录
        },
    })

    if data.get("code") != 0:
        raise RuntimeError(f"创建导入任务失败: {data}")

    ticket = data.get("data", {}).get("ticket", "")
    if not ticket:
        raise RuntimeError(f"创建导入任务成功但未获取到 ticket: {data}")

    _log(f"导入任务创建成功: ticket={ticket}")
    return ticket


def poll_import_result(token: str, ticket: str,
                       max_retries: int = 0) -> str:
    """
    轮询导入任务结果，返回文档 URL

    使用接口: GET /open-apis/drive/v1/import_tasks/{ticket}

    Args:
        token: access_token
        ticket: 导入任务 ticket
        max_retries: 最大轮询次数，0 表示使用默认值
    """
    poll_max = max_retries or IMPORT_POLL_MAX_RETRIES
    url = f"{FEISHU_BASE_URL}/open-apis/drive/v1/import_tasks/{ticket}"

    for i in range(poll_max):
        time.sleep(IMPORT_POLL_INTERVAL)
        _log(f"轮询导入结果 (第{i + 1}/{poll_max}次)...")

        try:
            data = _api_get(url, token)
        except Exception as e:
            _log(f"轮询请求异常: {e}")
            continue

        if data.get("code") != 0:
            _log(f"轮询返回错误: {data}")
            continue

        result = data.get("data", {}).get("result", {})
        job_status = result.get("job_status")
        job_error = result.get("job_error_msg", "")
        doc_token = result.get("token", "")
        doc_url = result.get("url", "")

        if doc_url:
            _log(f"导入成功: {doc_url}")
            return doc_url
        if doc_token:
            doc_url = f"{FEISHU_DOC_URL_PREFIX}/docx/{doc_token}"
            _log(f"导入成功: {doc_url}")
            return doc_url

        if job_status == 2:
            raise RuntimeError(
                f"导入任务失败: status={job_status}, error={job_error}"
            )

        _log(f"  状态: job_status={job_status}, msg={job_error}")

    raise RuntimeError(f"导入任务轮询超时 (ticket={ticket}, 共{poll_max}次)")


def create_wiki_node(token: str, title: str, parent_token: str = "") -> dict:
    """
    在 Wiki 知识库中创建一个节点（用作目录）

    使用接口: POST /open-apis/wiki/v2/spaces/{space_id}/nodes

    Args:
        token: access_token
        title: 节点标题
        parent_token: 父节点 token（为空则使用默认值）

    Returns:
        {"node_token": "...", "obj_token": "...", "wiki_url": "..."}
    """
    if not FEISHU_WIKI_SPACE_ID:
        raise RuntimeError("未配置 FEISHU_WIKI_SPACE_ID，无法创建 Wiki 节点")

    parent = parent_token or FEISHU_WIKI_PARENT_TOKEN
    if not parent:
        raise RuntimeError("未配置 FEISHU_WIKI_PARENT_TOKEN，无法创建 Wiki 节点")

    _log(f"创建 Wiki 目录节点: {title} (parent={parent})")

    url = f"{FEISHU_BASE_URL}/open-apis/wiki/v2/spaces/{FEISHU_WIKI_SPACE_ID}/nodes"
    data = _api_post_json(url, token, {
        "obj_type": "docx",
        "parent_node_token": parent,
        "node_type": "origin",
        "title": title,
    })

    if data.get("code") != 0:
        raise RuntimeError(f"创建 Wiki 节点失败: {data}")

    node = data.get("data", {}).get("node", {})
    node_token = node.get("node_token", "")
    obj_token = node.get("obj_token", "")

    if not node_token:
        raise RuntimeError(f"创建 Wiki 节点成功但未返回 node_token: {data}")

    wiki_url = f"{FEISHU_DOC_URL_PREFIX}/wiki/{node_token}"
    _log(f"Wiki 目录节点创建成功: {wiki_url}")

    return {
        "node_token": node_token,
        "obj_token": obj_token,
        "wiki_url": wiki_url,
    }


def _get_wiki_node_by_obj_token(token: str, obj_token: str,
                                max_retries: int = 5) -> str:
    """
    通过文档 obj_token 查询 Wiki 节点信息

    使用接口: GET /open-apis/wiki/v2/spaces/get_node?token=xxx&obj_type=docx
    在 move_docs_to_wiki 异步完成后，通过此接口获取 wiki URL。

    Returns:
        Wiki URL（成功）或空字符串（失败/超时）
    """
    url = (
        f"{FEISHU_BASE_URL}/open-apis/wiki/v2/spaces/get_node"
        f"?token={obj_token}&obj_type=docx"
    )
    for attempt in range(1, max_retries + 1):
        time.sleep(1)
        try:
            data = _api_get(url, token)
            if data.get("code") == 0:
                node = data.get("data", {}).get("node", {})
                node_token = node.get("node_token", "")
                if node_token:
                    wiki_url = f"{FEISHU_DOC_URL_PREFIX}/wiki/{node_token}"
                    _log(f"文档已移动到 Wiki: {wiki_url}")
                    return wiki_url

            _log(f"查询 Wiki 节点(第{attempt}次): code={data.get('code')}, msg={data.get('msg', '')}")

        except Exception as e:
            _log(f"查询 Wiki 节点异常(第{attempt}次): {e}")

    _log(f"查询 Wiki 节点超时(共{max_retries}次)，移动可能仍在进行中")
    return ""


def move_doc_to_wiki(token: str, doc_url: str, parent_token: str = "") -> str:
    """
    将文档移动到 Wiki 知识库

    使用接口: POST /open-apis/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki

    Args:
        token: access_token
        doc_url: 文档 URL
        parent_token: 指定父节点 token（为空则使用环境变量默认值）

    Returns:
        Wiki URL（如果移动成功），否则返回原始 doc_url
    """
    wiki_parent = parent_token or FEISHU_WIKI_PARENT_TOKEN

    if not FEISHU_WIKI_SPACE_ID:
        _log("未配置 FEISHU_WIKI_SPACE_ID，跳过移动到 Wiki")
        return doc_url

    if not wiki_parent:
        _log("未配置 FEISHU_WIKI_PARENT_TOKEN，跳过移动到 Wiki")
        return doc_url

    # 从 URL 中解析 doc_token
    doc_token = _parse_doc_token(doc_url)
    if not doc_token:
        _log(f"无法从 URL 解析 doc_token: {doc_url}，跳过移动到 Wiki")
        return doc_url

    _log(f"移动文档到 Wiki (space={FEISHU_WIKI_SPACE_ID}, parent={wiki_parent})...")

    try:
        url = (
            f"{FEISHU_BASE_URL}/open-apis/wiki/v2/spaces/"
            f"{FEISHU_WIKI_SPACE_ID}/nodes/move_docs_to_wiki"
        )
        data = _api_post_json(url, token, {
            "parent_wiki_token": wiki_parent,
            "obj_type": "docx",
            "obj_token": doc_token,
        })

        if data.get("code") == 0:
            resp_data = data.get("data", {})

            # 同步返回 node 的情况
            wiki_node = resp_data.get("node", {})
            node_token = wiki_node.get("node_token", "")
            if node_token:
                wiki_url = f"{FEISHU_DOC_URL_PREFIX}/wiki/{node_token}"
                _log(f"文档已移动到 Wiki: {wiki_url}")
                return wiki_url

            # 异步返回 task_id 的情况 → 通过 obj_token 查询 Wiki 节点
            task_id = resp_data.get("task_id", "")
            if task_id:
                _log(f"移动任务已提交(task_id={task_id})，等待完成后查询节点...")
                wiki_url = _get_wiki_node_by_obj_token(token, doc_token)
                if wiki_url:
                    return wiki_url

        _log(f"移动到 Wiki 返回: {data}（不影响主流程，使用原始文档 URL）")
        return doc_url

    except Exception as e:
        _log(f"移动到 Wiki 异常: {e}（不影响主流程，使用原始文档 URL）")
        return doc_url


def _parse_doc_token(doc_url: str) -> str:
    """从飞书文档 URL 中解析 document token"""
    patterns = [
        r"feishu\.cn/docx/([a-zA-Z0-9_-]+)",
        r"feishu\.cn/wiki/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, doc_url)
        if match:
            return match.group(1)
    return ""


# ==================== Markdown 预处理 ====================

# 飞书 Import Task API 对 Markdown 表格数量有限制（超过约 6 个表格会导致导入失败）
# 超出限制时，将多余的表格转换为可读的文本列表格式
MAX_TABLES = 6

# 飞书 Import Task API 对单个表格单元格长度有限制，超长内容导致 status=2 失败
MAX_TABLE_CELL_LEN = 200


def _sanitize_for_import(markdown: str) -> str:
    """
    清理飞书 Import Task API 不兼容的内容：
    1. 替换 emoji 为文本标记（emoji 在表格中导致 Import Task status=2 失败）
    2. 截断过长的表格单元格内容
    """
    for emoji_char, replacement in EMOJI_REPLACEMENTS.items():
        markdown = markdown.replace(emoji_char, replacement)

    # 兜底：移除其余 emoji（BMP 之外的 Unicode 字符和常见符号块）
    markdown = re.sub(
        r'[\U0001F300-\U0001F9FF\U00002702-\U000027B0\U0000FE0F]',
        '',
        markdown,
    )

    # 截断表格中过长的单元格
    lines = markdown.split('\n')
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and '|' in stripped[1:]:
            cells = stripped.split('|')
            truncated = []
            for cell in cells:
                if len(cell.strip()) > MAX_TABLE_CELL_LEN:
                    cell = ' ' + cell.strip()[:MAX_TABLE_CELL_LEN] + '... '
                truncated.append(cell)
            output.append('|'.join(truncated))
        else:
            output.append(line)
    return '\n'.join(output)


def _convert_table_to_text(table_lines: list) -> list:
    """
    将 Markdown 表格转为文本列表格式

    | A | B | C |       →    **A**: B - C
    |---|---|---|       →    (分隔线去掉)
    | x | y | z |       →    **x**: y - z
    """
    result = []
    headers = []
    for line in table_lines:
        stripped = line.strip()
        # 跳过分隔行
        if re.match(r'^\|[\s\-:|]+\|$', stripped):
            continue
        # 解析单元格
        cells = [c.strip() for c in stripped.split('|')]
        cells = [c for c in cells if c]  # 去掉空字符串
        if not cells:
            continue
        if not headers:
            headers = cells
            continue
        # 数据行：用 "header: value" 格式
        if len(cells) == 1:
            result.append(f"- {cells[0]}")
        elif len(cells) == 2:
            result.append(f"- **{cells[0]}**: {cells[1]}")
        else:
            result.append(f"- **{cells[0]}**: {' | '.join(cells[1:])}")
    return result


def preprocess_markdown(markdown: str) -> str:
    """
    预处理 Markdown 内容，解决飞书 Import Task API 的表格数量限制。
    当表格数量超过 MAX_TABLES 时，将多余的表格转换为列表格式。
    """
    lines = markdown.split('\n')
    table_count = 0
    in_table = False
    current_table = []
    output = []

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith('|') and '|' in stripped[1:]

        if is_table_line:
            if not in_table:
                in_table = True
                current_table = []
                table_count += 1
            current_table.append(line)
        else:
            if in_table:
                # 表格结束，决定是保留还是转换
                in_table = False
                if table_count <= MAX_TABLES:
                    # 保留原始表格
                    output.extend(current_table)
                else:
                    # 转为文本列表
                    converted = _convert_table_to_text(current_table)
                    output.extend(converted)
                current_table = []
            output.append(line)

    # 处理文件末尾的表格
    if in_table and current_table:
        if table_count <= MAX_TABLES:
            output.extend(current_table)
        else:
            converted = _convert_table_to_text(current_table)
            output.extend(converted)

    result = '\n'.join(output)
    if table_count > MAX_TABLES:
        _log(
            f"Markdown 预处理：共 {table_count} 个表格，"
            f"保留前 {MAX_TABLES} 个，后 {table_count - MAX_TABLES} 个已转为列表格式"
        )
    return result


# ==================== 增量写入 (Docx Block API) ====================

# Feishu block_type: heading1=3 ... heading6=8, text=2, bullet=10, ordered=11,
# code=12, divider=22

CODE_LANG_MAP = {
    'python': 49, 'py': 49, 'javascript': 30, 'js': 30,
    'typescript': 63, 'ts': 63, 'java': 29, 'go': 22, 'golang': 22,
    'bash': 7, 'sh': 7, 'shell': 60, 'json': 28, 'yaml': 67, 'yml': 67,
    'xml': 66, 'html': 24, 'css': 12, 'scss': 55, 'sql': 56,
    'c': 10, 'cpp': 9, 'c++': 9, 'rust': 53, 'ruby': 52, 'rb': 52,
    'swift': 61, 'kotlin': 32, 'kt': 32, 'php': 43, 'markdown': 39,
    'md': 39, 'dockerfile': 18, 'diff': 69, 'graphql': 71, 'toml': 75,
}

BLOCKS_PER_BATCH = 10
BATCH_INTERVAL = 1.0
MAX_TEXT_RUN_LEN = 2000
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _sanitize_block_text(text: str) -> str:
    """清理 Block API 不接受的控制字符。"""
    if not text:
        return ""
    sanitized = text.replace("\r\n", "\n").replace("\r", "\n")
    return CONTROL_CHAR_PATTERN.sub("", sanitized)


def _parse_inline_elements(text: str) -> list:
    """解析 Markdown 内联格式 (**bold**, *italic*, `code`) 为飞书 text elements"""
    text = _sanitize_block_text(text)
    if not text:
        return [{"text_run": {"content": ""}}]

    elements = []
    pattern = re.compile(
        r'\*\*(.+?)\*\*'
        r'|`([^`]+)`'
        r'|\*([^*]+)\*'
    )

    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            plain = text[last_end:match.start()]
            if plain:
                elements.append({"text_run": {"content": plain}})

        bold, code, italic = match.group(1), match.group(2), match.group(3)
        if bold is not None:
            elements.append({
                "text_run": {
                    "content": bold,
                    "text_element_style": {"bold": True},
                }
            })
        elif code is not None:
            elements.append({
                "text_run": {
                    "content": code,
                    "text_element_style": {"inline_code": True},
                }
            })
        elif italic is not None:
            elements.append({
                "text_run": {
                    "content": italic,
                    "text_element_style": {"italic": True},
                }
            })

        last_end = match.end()

    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            elements.append({"text_run": {"content": remaining}})

    if not elements:
        elements.append({"text_run": {"content": text}})

    return elements


def _split_long_content(content: str) -> list:
    """将超长内容拆分为多个 text_run（飞书单个 text_run 上限约 3000 字符）"""
    content = _sanitize_block_text(content)
    if len(content) <= MAX_TEXT_RUN_LEN:
        return [{"text_run": {"content": content}}]
    runs = []
    for i in range(0, len(content), MAX_TEXT_RUN_LEN):
        runs.append({"text_run": {"content": content[i:i + MAX_TEXT_RUN_LEN]}})
    return runs


def _extract_plain_text_from_elements(elements: list) -> str:
    """从飞书 elements 中提取纯文本。"""
    parts = []
    for element in elements or []:
        text_run = element.get("text_run", {})
        content = text_run.get("content", "")
        if content:
            parts.append(content)
    return _sanitize_block_text("".join(parts)).strip()


def _block_to_plain_text(block: dict) -> str:
    """将复杂 block 降级为纯文本内容，便于兜底重试。"""
    if not isinstance(block, dict):
        return ""

    for key in (
        "text", "bullet", "ordered", "heading1", "heading2", "heading3",
        "heading4", "heading5", "heading6",
    ):
        node = block.get(key)
        if isinstance(node, dict):
            text = _extract_plain_text_from_elements(node.get("elements", []))
            if text:
                return text

    code_node = block.get("code")
    if isinstance(code_node, dict):
        text = _extract_plain_text_from_elements(code_node.get("elements", []))
        if text:
            return text

    return ""


def _downgrade_block_to_text(block: dict) -> dict | None:
    """将单个 block 降级为纯文本段落，降低 invalid param 风险。"""
    text = _block_to_plain_text(block)
    if not text:
        return None
    return {
        "block_type": 2,
        "text": {"elements": _split_long_content(text)},
    }


def markdown_to_blocks(markdown: str) -> list:
    """
    将 Markdown 转为飞书 Docx Block 结构列表。

    表格自动转为 bullet 列表（Block API 不支持直接创建表格）。
    目标是内容完整 + 基本可读，不追求完美还原样式。
    """
    lines = markdown.split('\n')
    blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # --- Code block: ```lang ... ``` ---
        if stripped.startswith('```'):
            lang = stripped[3:].strip().lower()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            code_content = '\n'.join(code_lines)
            if code_content:
                blocks.append({
                    "block_type": 12,
                    "code": {
                        "elements": _split_long_content(code_content),
                        "style": {"language": CODE_LANG_MAP.get(lang, 1)},
                    },
                })
            continue

        # --- Table: | ... | → bullet list ---
        if stripped.startswith('|') and '|' in stripped[1:]:
            table_lines = [line]
            i += 1
            while i < n and lines[i].strip().startswith('|') and '|' in lines[i].strip()[1:]:
                table_lines.append(lines[i])
                i += 1
            for item in _convert_table_to_text(table_lines):
                text = item.lstrip('- ').strip()
                if text:
                    blocks.append({
                        "block_type": 10,
                        "bullet": {"elements": _parse_inline_elements(text)},
                    })
            continue

        # --- Heading: # ~ ###### ---
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            key = f"heading{level}"
            blocks.append({
                "block_type": 2 + level,
                key: {"elements": _parse_inline_elements(text)},
            })
            i += 1
            continue

        # --- Divider: --- / *** / ___ ---
        if re.match(r'^[-*_]{3,}$', stripped):
            blocks.append({"block_type": 22, "divider": {}})
            i += 1
            continue

        # --- Quote: > text → plain text (container blocks too complex) ---
        if stripped.startswith('>'):
            text = stripped[1:].strip()
            if text:
                blocks.append({
                    "block_type": 2,
                    "text": {"elements": _parse_inline_elements(text)},
                })
            i += 1
            continue

        # --- Bullet list: - / * / + ---
        bullet_match = re.match(r'^[-*+]\s+(.+)$', stripped)
        if bullet_match:
            blocks.append({
                "block_type": 10,
                "bullet": {"elements": _parse_inline_elements(bullet_match.group(1))},
            })
            i += 1
            continue

        # --- Ordered list: N. text ---
        ordered_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if ordered_match:
            blocks.append({
                "block_type": 11,
                "ordered": {"elements": _parse_inline_elements(ordered_match.group(1))},
            })
            i += 1
            continue

        # --- Regular text paragraph ---
        blocks.append({
            "block_type": 2,
            "text": {"elements": _parse_inline_elements(stripped)},
        })
        i += 1

    return blocks


def create_document_empty(token: str, title: str) -> str:
    """
    创建空白飞书文档，返回 document_id

    使用接口: POST /open-apis/docx/v1/documents
    """
    _log(f"创建空白文档: {title}")

    url = f"{FEISHU_BASE_URL}/open-apis/docx/v1/documents"
    data = _api_post_json(url, token, {
        "title": title or "变更分析报告",
        "folder_token": "",
    })

    if data.get("code") != 0:
        raise RuntimeError(f"创建空白文档失败: {data}")

    document = data.get("data", {}).get("document", {})
    document_id = document.get("document_id", "")
    if not document_id:
        raise RuntimeError(f"创建文档成功但未返回 document_id: {data}")

    _log(f"空白文档创建成功: document_id={document_id}")
    return document_id


def _get_document_revision(token: str, document_id: str) -> int:
    """查询文档当前 revision_id，失败时返回 -1 作为兜底"""
    try:
        url = f"{FEISHU_BASE_URL}/open-apis/docx/v1/documents/{document_id}"
        data = _api_get(url, token)
        if data.get("code") == 0:
            revision = data.get("data", {}).get("document", {}).get("revision_id", -1)
            return int(revision)
    except Exception as e:
        _log(f"查询文档 revision 失败，使用 -1 兜底: {e}")
    return -1


def append_blocks_to_document(
        token: str, document_id: str, blocks: list,
        batch_size: int = BLOCKS_PER_BATCH, max_retries: int = 3,
):
    """
    分批追加 blocks 到飞书文档。

    使用接口: POST /open-apis/docx/v1/documents/{id}/blocks/{id}/children
    每批最多 batch_size 个 blocks，批次间间隔 BATCH_INTERVAL 秒。
    """
    total = len(blocks)
    written = 0
    total_batches = (total + batch_size - 1) // batch_size

    revision_id = _get_document_revision(token, document_id)

    base_url = (
        f"{FEISHU_BASE_URL}/open-apis/docx/v1/documents/{document_id}"
        f"/blocks/{document_id}/children"
    )

    def _append_batch(batch: list, label: str, current_revision_id: int) -> tuple[bool, int, dict]:
        last_data = {}
        for attempt in range(1, max_retries + 1):
            url = f"{base_url}?document_revision_id={current_revision_id}"
            try:
                data = _api_post_json(url, token, {
                    "children": batch,
                    "index": -1,
                })
                last_data = data
                if data.get("code") == 0:
                    new_rev = (
                        data.get("data", {})
                        .get("document_revision_id", current_revision_id)
                    )
                    current_revision_id = int(new_rev)
                    _log(
                        f"{label}写入成功 ({len(batch)} blocks, rev={current_revision_id})"
                    )
                    return True, current_revision_id, data

                error_code = data.get('code')
                error_msg = data.get('msg', '')
                _log(
                    f"{label}写入失败(第{attempt}次): "
                    f"code={error_code}, msg={error_msg}"
                )
                if error_code == 1770001 and attempt < max_retries:
                    current_revision_id = _get_document_revision(token, document_id)
                    _log(f"{label}刷新 revision_id={current_revision_id} 后重试")
            except Exception as e:
                last_data = {'exception': str(e)}
                _log(f"{label}写入异常(第{attempt}次): {e}")

            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
        return False, current_revision_id, last_data

    for batch_start in range(0, total, batch_size):
        batch = blocks[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1

        label = f"批次 {batch_num}/{total_batches}"
        success, revision_id, error_data = _append_batch(batch, label, revision_id)
        if success:
            written += len(batch)
            _log(f"{label}累计进度: {written}/{total} blocks")
        else:
            _log(f"{label}进入单块降级重试")
            for block_index, block in enumerate(batch, start=1):
                single_label = f"{label} 第{block_index}块"
                single_success, revision_id, single_error = _append_batch(
                    [block], single_label, revision_id,
                )
                if not single_success:
                    downgraded = _downgrade_block_to_text(block)
                    if downgraded:
                        _log(f"{single_label}降级为纯文本后重试")
                        single_success, revision_id, single_error = _append_batch(
                            [downgraded], f"{single_label}(降级)", revision_id,
                        )
                    if not single_success:
                        _error(
                            f"{single_label}最终失败: {single_error or error_data}"
                        )
                        continue
                written += 1
                _log(f"{single_label}累计进度: {written}/{total} blocks")

        if written < min(batch_start + len(batch), total) and not success:
            _error(
                f"{label}存在未写入 blocks，已尝试单块降级补救"
            )

        if batch_start + batch_size < total:
            time.sleep(BATCH_INTERVAL)

    _log(f"增量写入完成: 成功 {written}/{total} blocks")
    if written < total:
        raise RuntimeError(f"Docx Block API 写入不完整: 成功 {written}/{total} blocks")


def create_doc_incremental(token: str, title: str, markdown: str) -> str:
    """
    通过 Docx Block API 增量写入文档（Import Task 失败时的兜底方案）。

    流程: 创建空白文档 → 等待一致性 → Markdown 转 blocks → 分批写入 → 返回文档 URL
    表格自动转为列表格式，代码块完整保留。
    """
    document_id = create_document_empty(token, title)
    doc_url = f"{FEISHU_DOC_URL_PREFIX}/docx/{document_id}"
    _log(f"空白文档已创建: {doc_url}")

    time.sleep(2)

    blocks = markdown_to_blocks(markdown)
    _log(f"Markdown 转换为 {len(blocks)} 个 blocks")

    if blocks:
        append_blocks_to_document(token, document_id, blocks)
    else:
        _log("Markdown 内容为空，跳过 block 写入")

    return doc_url


# ==================== 主命令 ====================

def _calc_poll_retries(markdown_size: int) -> int:
    """根据 Markdown 内容大小动态计算 Import Task 轮询次数"""
    base = IMPORT_POLL_MAX_RETRIES
    extra = markdown_size // (50 * 1024) * 5
    return min(base + extra, 60)


def cmd_create(title: str, markdown: str, move_to_wiki: bool = True,
               wiki_parent_token: str = ""):
    """
    创建飞书文档的完整流程

    策略 1: Import Task API — 上传 Markdown 一次性导入（保留完整格式），失败自动重试 1 次
    策略 2: Docx Block API — 创建空文档 + 分批写入 blocks（兜底，表格降级为列表）

    Args:
        title: 文档标题
        markdown: Markdown 内容
        move_to_wiki: 是否移动到 Wiki
        wiki_parent_token: 指定 Wiki 父节点 token（为空则使用环境变量默认值）
    """
    token = get_tenant_access_token()
    raw_size = len(markdown)

    markdown = _sanitize_for_import(markdown)
    markdown = preprocess_markdown(markdown)
    poll_retries = _calc_poll_retries(raw_size)

    _log(f"文档参数: size={raw_size}, sanitized_size={len(markdown)}, "
         f"poll_retries={poll_retries}")

    # 策略 1: Import Task API（最多 2 次尝试）
    doc_url = None
    import_attempts = 2
    for attempt in range(1, import_attempts + 1):
        try:
            file_token = upload_markdown_file(token, title, markdown)
            ticket = create_import_task(token, file_token, title)
            doc_url = poll_import_result(token, ticket, max_retries=poll_retries)
            _log(f"Import Task API 成功(第{attempt}次): {doc_url}")
            break
        except Exception as e:
            _log(f"Import Task API 失败(第{attempt}/{import_attempts}次): {e}")
            if attempt < import_attempts:
                _log("等待 3 秒后重试 Import Task...")
                time.sleep(3)

    # 策略 2: 增量写入兜底
    if not doc_url:
        _log("切换到增量写入模式 (Docx Block API)...")
        doc_url = create_doc_incremental(token, title, markdown)

    wiki_url = ""
    if move_to_wiki:
        final_url = move_doc_to_wiki(token, doc_url, wiki_parent_token)
        if final_url != doc_url:
            wiki_url = final_url
    else:
        final_url = doc_url

    result = {
        "url": final_url,
        "doc_url": doc_url,
        "title": title,
    }
    if wiki_url:
        result["wiki_url"] = wiki_url

    print(json.dumps(result, ensure_ascii=False, indent=2))
    _log(f"飞书文档创建完成: {final_url}")


def cmd_create_dir(title: str, parent_token: str = ""):
    """
    在 Wiki 知识库中创建一个目录节点

    输出 JSON 到 stdout: {"node_token": "...", "wiki_url": "..."}
    """
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        _error("环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET 未配置")
        sys.exit(1)

    token = get_tenant_access_token()
    result = create_wiki_node(token, title, parent_token)
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ==================== 入口 ====================

USAGE = """\
飞书文档创建工具

子命令:
  create      创建飞书文档（从文件或 stdin 读取 Markdown）
  create-dir  在 Wiki 中创建一个目录节点（用于归档多个文档）

用法:
  # 创建文档并移动到 Wiki 默认目录
  python3 create_feishu_doc.py create --title "报告标题" --file report.md

  # 创建文档并移动到指定 Wiki 目录
  python3 create_feishu_doc.py create --title "子文档" --file doc.md --wiki-parent <node_token>

  # 创建文档但不移动到 Wiki
  python3 create_feishu_doc.py create --title "标题" --file doc.md --no-wiki

  # 创建 Wiki 目录节点
  python3 create_feishu_doc.py create-dir --title "需求-变更分析-2026021315"

  # 创建 Wiki 目录节点（指定父节点）
  python3 create_feishu_doc.py create-dir --title "目录名" --parent <parent_token>

环境变量:
  FEISHU_APP_ID            飞书应用 App ID（必需）
  FEISHU_APP_SECRET        飞书应用 App Secret（必需）
  FEISHU_BASE_URL          飞书 API 基础地址（默认 https://open.feishu.cn）
  FEISHU_WIKI_SPACE_ID     Wiki 空间 ID（移动到 Wiki 时必需）
  FEISHU_WIKI_PARENT_TOKEN Wiki 父节点 token
  FEISHU_DOC_URL_PREFIX    文档 URL 前缀（默认 https://xd.feishu.cn）

多文档输出示例:
  # 1. 创建目录
  DIR=$(python3 create_feishu_doc.py create-dir --title "优惠券-变更分析-2026021315")
  NODE_TOKEN=$(echo $DIR | python3 -c "import sys,json; print(json.load(sys.stdin)['node_token'])")

  # 2. 在目录下创建子文档
  python3 create_feishu_doc.py create --title "变更分析总报告" --file report.md --wiki-parent $NODE_TOKEN
  python3 create_feishu_doc.py create --title "MR分析详情" --file mr_analysis.md --wiki-parent $NODE_TOKEN
  python3 create_feishu_doc.py create --title "测试覆盖矩阵" --file coverage.md --wiki-parent $NODE_TOKEN
"""


def _parse_args(argv: list) -> dict:
    """解析命令行参数"""
    args = {
        "title": "",
        "file_path": "",
        "move_to_wiki": True,
        "wiki_parent": "",
        "parent": "",
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--title" and i + 1 < len(argv):
            args["title"] = argv[i + 1]
            i += 2
        elif arg == "--file" and i + 1 < len(argv):
            args["file_path"] = argv[i + 1]
            i += 2
        elif arg == "--no-wiki":
            args["move_to_wiki"] = False
            i += 1
        elif arg == "--wiki-parent" and i + 1 < len(argv):
            args["wiki_parent"] = argv[i + 1]
            i += 2
        elif arg == "--parent" and i + 1 < len(argv):
            args["parent"] = argv[i + 1]
            i += 2
        else:
            _error(f"未知参数: {arg}")
            print(USAGE, file=sys.stderr)
            sys.exit(1)
    return args


def _read_markdown(file_path: str) -> str:
    """读取 Markdown 内容（从文件或 stdin）"""
    if file_path:
        if not os.path.isfile(file_path):
            _error(f"文件不存在: {file_path}")
            sys.exit(1)
        _log(f"从文件读取: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    else:
        if sys.stdin.isatty():
            _error("未指定 --file 且 stdin 无数据。请通过 --file 或管道提供 Markdown 内容。")
            sys.exit(1)
        _log("从 stdin 读取 Markdown 内容...")
        return sys.stdin.read()


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE, file=sys.stderr)
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    command = sys.argv[1]

    if command not in ("create", "create-dir"):
        _error(f"未知子命令: {command}")
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # 检查环境变量
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        _error("环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET 未配置")
        sys.exit(1)

    args = _parse_args(sys.argv[2:])

    if not args["title"]:
        _error("--title 参数是必需的")
        sys.exit(1)

    try:
        if command == "create-dir":
            cmd_create_dir(args["title"], args["parent"])

        elif command == "create":
            markdown = _read_markdown(args["file_path"])
            if not markdown.strip():
                _error("Markdown 内容为空")
                sys.exit(1)
            _log(f"Markdown 内容长度: {len(markdown)} 字符")
            cmd_create(
                args["title"], markdown,
                move_to_wiki=args["move_to_wiki"],
                wiki_parent_token=args["wiki_parent"],
            )

    except Exception as e:
        import traceback
        _error(f"执行失败: {e}")
        _error(f"详细错误:\n{traceback.format_exc()}")
        print(json.dumps({
            "error": True,
            "message": str(e),
        }, ensure_ascii=False), file=sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
