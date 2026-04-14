#!/usr/bin/env python3
"""
飞书文档图文获取工具 — 供 AI Agent 获取飞书文档的完整内容（文字+图片）

使用 Blocks API 获取文档结构，解析为 Markdown 格式，
同时下载文档中的图片到本地目录，供 AI 通过 Read 工具查看。

用法:
    # 从 URL 获取（自动识别 wiki/docx/docs 链接）
    python3 fetch_feishu_doc.py --url "https://xxx.feishu.cn/wiki/AbCdEfG" --output-dir .

    # 直接指定 document_id
    python3 fetch_feishu_doc.py --doc-id "AbCdEfG" --output-dir .

    # 跳过图片下载（仅获取文字）
    python3 fetch_feishu_doc.py --url "..." --output-dir . --skip-images

环境变量:
    FEISHU_APP_ID       - 飞书应用 App ID（必需）
    FEISHU_APP_SECRET   - 飞书应用 App Secret（必需）
    FEISHU_BASE_URL     - 飞书 API 基础地址（默认 https://open.feishu.cn）
    FEISHU_HOST         - 同 FEISHU_BASE_URL（向后兼容，优先使用 FEISHU_BASE_URL）

输出:
    stdout: Markdown 格式的文档内容（图片以 ![image](images/xxx.jpg) 引用）
    stderr: JSON 元数据 {"title": "...", "images": [...], "image_dir": "..."}
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

# ==================== 配置 ====================

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_BASE_URL = (
    os.environ.get("FEISHU_BASE_URL")
    or os.environ.get("FEISHU_HOST")
    or "https://open.feishu.cn"
)


# ==================== 日志 ====================

def log(msg):
    print(f"[LOG] [fetch_feishu_doc] {msg}", file=sys.stderr)


def log_error(msg):
    print(f"[LOG] [fetch_feishu_doc] ERROR: {msg}", file=sys.stderr)


# ==================== 飞书 API ====================

_access_token = None
_token_expire_time = 0


def get_access_token():
    global _access_token, _token_expire_time
    if _access_token and time.time() < (_token_expire_time - 300):
        return _access_token

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        raise RuntimeError(
            "FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量未设置"
        )

    url = f"{FEISHU_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
    payload = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(
            f"获取 tenant_access_token 失败: HTTP {e.code} {e.reason}, "
            f"请检查 FEISHU_APP_ID/FEISHU_APP_SECRET 配置, response={body}"
        ) from e

    if result.get("code") != 0:
        raise RuntimeError(f"获取 access_token 失败: {result.get('msg')}")

    _access_token = result["tenant_access_token"]
    _token_expire_time = time.time() + result.get("expire", 7200)
    return _access_token


def feishu_api_get(endpoint, params=None):
    token = get_access_token()
    url = f"{FEISHU_BASE_URL}{endpoint}"
    if params:
        qs = urllib.parse.urlencode(params)
        url += f"?{qs}" if "?" not in url else f"&{qs}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(
            f"飞书 API 请求失败: {e.code} {e.reason}, "
            f"endpoint={endpoint}, response={body}"
        ) from e


def download_media(media_token, output_path):
    token = get_access_token()
    url = f"{FEISHU_BASE_URL}/open-apis/drive/v1/medias/{media_token}/download"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception as e:
        log_error(f"下载图片失败 {media_token}: {e}")
        return False


def fetch_sheet_content(sheet_token):
    """通过飞书 Sheets API 获取电子表格内容，返回二维数组

    sheet_token 格式为 "{spreadsheet_token}_{sheet_id}"
    """
    parts = sheet_token.split('_', 1)
    if len(parts) != 2:
        log_error(f"无法解析 sheet token: {sheet_token}")
        return None

    spreadsheet_token, sheet_id = parts
    try:
        result = feishu_api_get(
            f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}",
        )
        if result.get('code') != 0:
            log_error(
                f"获取 sheet 内容失败: code={result.get('code')}, "
                f"msg={result.get('msg')}, token={sheet_token[:8]}..."
            )
            return None
        return result.get('data', {}).get('valueRange', {}).get('values', [])
    except Exception as e:
        log_error(f"获取 sheet 内容异常: {e}, token={sheet_token[:8]}...")
        return None


def download_board_thumbnail(board_id, output_path):
    token = get_access_token()
    url = f"{FEISHU_BASE_URL}/open-apis/board/v1/whiteboards/{board_id}/download_as_image"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception as e:
        log_error(f"下载画板缩略图失败 {board_id}: {e}")
        return False


# ==================== 文档 URL 解析 ====================

def parse_document_url(url):
    """从飞书文档 URL 中提取 document_id，返回 (doc_type, document_id)"""
    # wiki 链接: /wiki/AbCdEfG 或 /wiki/AbCdEfG#anchor
    m = re.search(r'feishu\.cn/wiki/([a-zA-Z0-9]+)', url)
    if m:
        return "wiki", m.group(1)

    # docx 链接: /docx/AbCdEfG
    m = re.search(r'feishu\.cn/docx/([a-zA-Z0-9]+)', url)
    if m:
        return "docx", m.group(1)

    # docs 链接: /docs/AbCdEfG
    m = re.search(r'feishu\.cn/docs/([a-zA-Z0-9]+)', url)
    if m:
        return "docs", m.group(1)

    raise ValueError(f"无法从 URL 中解析 document_id: {url}")


SUPPORTED_WIKI_OBJ_TYPES = {"doc", "docx"}


def resolve_wiki_to_docx_id(wiki_token):
    """将 wiki token 解析为实际的 docx document_id

    飞书 wiki/v2/spaces/get_node 返回两个类型字段：
    - node_type: origin（实体）/ shortcut（快捷方式）
    - obj_type:  doc / docx / sheet / bitable / mindnote / file
    仅 obj_type 为 doc/docx 的节点可通过 Blocks API 获取内容。

    返回 (obj_token, title, space_id, node_token, has_child)
    """
    result = feishu_api_get(
        "/open-apis/wiki/v2/spaces/get_node",
        params={"token": wiki_token},
    )
    node = result.get("data", {}).get("node", {})
    obj_token = node.get("obj_token", wiki_token)
    obj_type = node.get("obj_type", "")
    title = node.get("title", "")
    space_id = node.get("space_id", "")
    node_token = node.get("node_token", wiki_token)
    has_child = node.get("has_child", False)

    if obj_type and obj_type not in SUPPORTED_WIKI_OBJ_TYPES:
        raise RuntimeError(
            f"不支持的 Wiki 文档类型: {obj_type}（token: {wiki_token}, 标题: {title}），"
            f"仅支持 doc/docx，bitable/sheet/mindnote 等类型无法通过 Blocks API 获取"
        )
    return obj_token, title, space_id, node_token, has_child


# ==================== Wiki 子文档遍历 ====================

def list_wiki_children(space_id, parent_node_token, max_children=10):
    """BFS 遍历 wiki 父节点下的所有子文档（含递归子节点），带熔断机制。

    返回 (fetched_nodes, skipped_nodes, truncated, total_found)
    - fetched_nodes: 可获取内容的子节点列表 [{node_token, obj_token, obj_type, title, depth}, ...]
    - skipped_nodes: 不支持类型的子节点 [{title, obj_type, reason}, ...]
    - truncated: 是否因达到上限而截断
    - total_found: 发现的子文档总数（含截断后未获取的）
    """
    from collections import deque

    fetched = []
    skipped = []
    total_found = 0
    truncated = False

    queue = deque()
    queue.append((parent_node_token, 1))

    while queue:
        current_token, depth = queue.popleft()
        page_token = None

        while True:
            params = {"parent_node_token": current_token, "page_size": "50"}
            if page_token:
                params["page_token"] = page_token

            try:
                result = feishu_api_get(
                    f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
                    params=params,
                )
            except RuntimeError as e:
                log_error(f"列举子节点失败 (parent={current_token}): {e}")
                break

            data = result.get("data", {})
            items = data.get("items", [])

            for item in items:
                total_found += 1
                obj_type = item.get("obj_type", "")
                child_title = item.get("title", "")
                child_node_token = item.get("node_token", "")
                child_has_child = item.get("has_child", False)

                if obj_type in SUPPORTED_WIKI_OBJ_TYPES:
                    if len(fetched) >= max_children:
                        truncated = True
                        continue
                    fetched.append({
                        "node_token": child_node_token,
                        "obj_token": item.get("obj_token", ""),
                        "obj_type": obj_type,
                        "title": child_title,
                        "depth": depth,
                    })
                else:
                    skipped.append({
                        "title": child_title,
                        "obj_type": obj_type,
                        "reason": "不支持的文档类型",
                    })

                if child_has_child and not truncated:
                    queue.append((child_node_token, depth + 1))

            page_token = data.get("page_token")
            if not data.get("has_more") or not page_token:
                break

        if truncated:
            break

    return fetched, skipped, truncated, total_found


# ==================== Blocks 获取 ====================

def fetch_all_blocks(document_id):
    """分页获取文档的所有 blocks"""
    all_blocks = []
    page_token = None

    while True:
        params = {"document_revision_id": "-1", "page_size": "500"}
        if page_token:
            params["page_token"] = page_token

        result = feishu_api_get(
            f"/open-apis/docx/v1/documents/{document_id}/blocks",
            params=params,
        )

        data = result.get("data", {})
        items = data.get("items", [])
        all_blocks.extend(items)

        page_token = data.get("page_token")
        if not page_token:
            break

    return all_blocks


# ==================== Block 文本提取 ====================

TEXT_FIELD_PATTERNS = [
    re.compile(r'^text$'),
    re.compile(r'^heading\d+$'),
    re.compile(r'^bullet$'),
    re.compile(r'^ordered$'),
    re.compile(r'^code$'),
    re.compile(r'^todo$'),
]


def get_block_text(block):
    """从 block 中提取纯文本内容"""
    text_obj = None
    for key in block.keys():
        if any(p.match(key) for p in TEXT_FIELD_PATTERNS):
            text_obj = block[key]
            break

    if not text_obj or not text_obj.get("elements"):
        return None

    parts = []
    for element in text_obj["elements"]:
        text_run = element.get("text_run")
        if text_run:
            parts.append(text_run.get("content", ""))
            continue
        mention_doc = element.get("mention_doc")
        if mention_doc:
            parts.append(mention_doc.get("title", "@文档"))
            continue
        mention_user = element.get("mention_user")
        if mention_user:
            parts.append("@用户")
            continue
        equation = element.get("equation")
        if equation:
            parts.append(equation.get("content", ""))
            continue
    return "".join(parts) or None


def get_block_code_language(block):
    """获取代码块的语言标识"""
    code_obj = block.get("code")
    if code_obj:
        style = code_obj.get("style", {})
        lang = style.get("language", 0)
        lang_map = {
            1: "plaintext", 2: "abap", 3: "ada", 4: "apache", 5: "apex",
            6: "assembly", 7: "bash", 8: "basic", 9: "bnf", 10: "c",
            11: "clojure", 12: "cmake", 13: "coffeescript", 14: "cpp",
            15: "csharp", 16: "css", 17: "dart", 18: "delphi", 19: "django",
            20: "dockerfile", 21: "elixir", 22: "erlang", 23: "fortran",
            24: "fsharp", 25: "gams", 26: "go", 27: "graphql", 28: "groovy",
            29: "haskell", 30: "html", 31: "http", 32: "java", 33: "javascript",
            34: "json", 35: "julia", 36: "kotlin", 37: "latex", 38: "lisp",
            39: "lua", 40: "makefile", 41: "markdown", 42: "matlab",
            43: "nginx", 44: "objectivec", 45: "ocaml", 46: "pascal",
            47: "perl", 48: "php", 49: "powershell", 50: "prolog",
            51: "protobuf", 52: "python", 53: "r", 54: "regex", 55: "ruby",
            56: "rust", 57: "sas", 58: "scala", 59: "scheme", 60: "scss",
            61: "shell", 62: "sql", 63: "swift", 64: "thrift", 65: "typescript",
            66: "vbnet", 67: "verilog", 68: "vhdl", 69: "visual_basic",
            70: "wasm", 71: "xml", 72: "yaml", 73: "zig",
        }
        return lang_map.get(lang, "")
    return ""


# ==================== Markdown 渲染 ====================

class MarkdownRenderer:
    """将飞书 blocks 递归渲染为 Markdown"""

    def __init__(self, blocks, image_dir, skip_images=False):
        self.block_dict = {b["block_id"]: b for b in blocks}
        self.image_dir = image_dir
        self.skip_images = skip_images
        self.images_downloaded = []
        self.lines = []

    def render(self):
        if not self.block_dict:
            return ""

        root_block = list(self.block_dict.values())[0]
        title = self._extract_title(root_block)

        children_ids = root_block.get("children", [])
        for child_id in children_ids:
            child = self.block_dict.get(child_id)
            if child:
                self._render_block(child, depth=0)

        return "\n".join(self.lines), title

    def _extract_title(self, root_block):
        try:
            page = root_block.get("page", {})
            elements = page.get("elements", [])
            if elements:
                return elements[0].get("text_run", {}).get("content", "")
        except (KeyError, IndexError):
            pass
        return ""

    def _render_block(self, block, depth=0):
        block_type = block.get("block_type", 0)
        text = get_block_text(block)

        if 3 <= block_type <= 11:
            level = block_type - 2
            self._render_heading(text or "", level)
        elif block_type == 2:
            self._render_paragraph(text)
        elif block_type == 12:
            self._render_bullet(text, depth)
        elif block_type == 13:
            self._render_ordered(text, depth)
        elif block_type == 14:
            self._render_code(block, text)
        elif block_type == 27:
            self._render_image(block)
        elif block_type == 30:
            self._render_sheet(block)
            return
        elif block_type == 31:
            self._render_table(block)
            return
        elif block_type == 15:
            self._render_quote(block, depth)
            return
        elif block_type == 43:
            self._render_board(block)
            return
        elif block_type == 22:
            self._render_divider()
        elif text:
            self.lines.append(text)
            self.lines.append("")

        children_ids = block.get("children", [])
        if children_ids and block_type not in (31, 15, 43):
            for child_id in children_ids:
                child = self.block_dict.get(child_id)
                if child:
                    self._render_block(child, depth=depth + 1)

    def _render_heading(self, text, level):
        prefix = "#" * min(level, 6)
        self.lines.append(f"{prefix} {text}")
        self.lines.append("")

    def _render_paragraph(self, text):
        if text:
            self.lines.append(text)
            self.lines.append("")

    def _render_bullet(self, text, depth):
        indent = "  " * depth
        if text:
            self.lines.append(f"{indent}- {text}")

    def _render_ordered(self, text, depth):
        indent = "  " * depth
        if text:
            self.lines.append(f"{indent}1. {text}")

    def _render_code(self, block, text):
        lang = get_block_code_language(block)
        self.lines.append(f"```{lang}")
        if text:
            self.lines.append(text)
        self.lines.append("```")
        self.lines.append("")

    def _render_image(self, block):
        image_data = block.get("image", {})
        img_token = image_data.get("token", "")
        if not img_token:
            return

        if self.skip_images:
            self.lines.append(f"[图片: {img_token}]")
            self.lines.append("")
            return

        filename = f"{img_token}.jpg"
        local_path = os.path.join(self.image_dir, filename)

        if not os.path.exists(local_path):
            os.makedirs(self.image_dir, exist_ok=True)
            success = download_media(img_token, local_path)
            if not success:
                self.lines.append(f"[图片下载失败: {img_token}]")
                self.lines.append("")
                return

        self.images_downloaded.append({
            "token": img_token,
            "path": os.path.join("images", filename),
            "width": image_data.get("width", 0),
            "height": image_data.get("height", 0),
        })

        rel_path = os.path.join("images", filename)
        self.lines.append(f"![image]({rel_path})")
        self.lines.append("")

    def _render_table(self, block):
        table_data = block.get("table", {})
        col_size = table_data.get("property", {}).get("column_size", 0)
        row_size = table_data.get("property", {}).get("row_size", 0)
        cell_ids = table_data.get("cells", [])
        merge_info = table_data.get("property", {}).get("merge_info", [])

        if not col_size or not cell_ids:
            return

        rows = []
        for r in range(row_size):
            row = []
            for c in range(col_size):
                idx = r * col_size + c
                if idx < len(merge_info):
                    mi = merge_info[idx]
                    if mi.get("col_span", 1) == 0 or mi.get("row_span", 1) == 0:
                        row.append("")
                        continue

                if idx < len(cell_ids):
                    cell_id = cell_ids[idx]
                    cell_block = self.block_dict.get(cell_id, {})
                    cell_text = self._collect_cell_text(cell_block)
                    row.append(cell_text)
                else:
                    row.append("")
            rows.append(row)

        if not rows:
            return

        max_cols = max(len(r) for r in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        self.lines.append(
            "| " + " | ".join(rows[0]) + " |"
        )
        self.lines.append(
            "| " + " | ".join(["---"] * max_cols) + " |"
        )
        for row in rows[1:]:
            self.lines.append(
                "| " + " | ".join(row) + " |"
            )
        self.lines.append("")

    def _collect_cell_text(self, cell_block):
        """递归收集表格单元格内的所有文本"""
        parts = []
        text = get_block_text(cell_block)
        if text:
            parts.append(text.replace("|", "\\|").replace("\n", " "))

        for child_id in cell_block.get("children", []):
            child = self.block_dict.get(child_id, {})
            child_text = get_block_text(child)
            if child_text:
                parts.append(child_text.replace("|", "\\|").replace("\n", " "))
            for grandchild_id in child.get("children", []):
                grandchild = self.block_dict.get(grandchild_id, {})
                gc_text = get_block_text(grandchild)
                if gc_text:
                    parts.append(gc_text.replace("|", "\\|").replace("\n", " "))
        return " ".join(parts) if parts else ""

    def _render_sheet(self, block):
        """渲染文档内嵌电子表格（block_type 30）：通过 Sheets API 获取内容"""
        sheet_data = block.get("sheet", {})
        sheet_token = sheet_data.get("token", "")
        if not sheet_token:
            self.lines.append("[此处包含电子表格，无法获取 token]")
            self.lines.append("")
            return

        values = fetch_sheet_content(sheet_token)
        if not values:
            self.lines.append("[此处包含电子表格，内容获取失败]")
            self.lines.append("")
            return

        rows = []
        for raw_row in values:
            rendered_cells = []
            has_content = False
            for cell_value in raw_row:
                cell_text = self._render_sheet_cell(cell_value)
                if cell_text.strip():
                    has_content = True
                rendered_cells.append(cell_text)
            if has_content:
                rows.append(rendered_cells)

        if not rows:
            self.lines.append("[此处包含空的电子表格]")
            self.lines.append("")
            return

        max_cols = max(len(r) for r in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        self.lines.append(
            "| " + " | ".join(rows[0]) + " |"
        )
        self.lines.append(
            "| " + " | ".join(["---"] * max_cols) + " |"
        )
        for row in rows[1:]:
            self.lines.append(
                "| " + " | ".join(row) + " |"
            )
        self.lines.append("")

    def _render_sheet_cell(self, cell_value):
        """将电子表格单元格值转为 Markdown 文本，支持 embed-image"""
        if cell_value is None:
            return ""
        if isinstance(cell_value, (int, float)):
            return str(cell_value).replace("|", "\\|")
        if isinstance(cell_value, str):
            return cell_value.replace("|", "\\|").replace("\n", " ")
        if isinstance(cell_value, list):
            parts = []
            for segment in cell_value:
                if isinstance(segment, dict):
                    parts.append(segment.get("text", ""))
                elif isinstance(segment, str):
                    parts.append(segment)
            return "".join(parts).replace("|", "\\|").replace("\n", " ")
        if (isinstance(cell_value, dict)
                and cell_value.get("type") == "embed-image"
                and cell_value.get("fileToken")):
            return self._download_sheet_image(cell_value)
        return str(cell_value).replace("|", "\\|").replace("\n", " ")

    def _download_sheet_image(self, cell_value):
        """下载电子表格中的嵌入图片，返回 Markdown 图片引用"""
        file_token = cell_value["fileToken"]
        width = cell_value.get("width", 0)
        height = cell_value.get("height", 0)

        if self.skip_images:
            return f"[图片: {file_token}]"

        filename = f"{file_token}.jpg"
        local_path = os.path.join(self.image_dir, filename)

        if not os.path.exists(local_path):
            os.makedirs(self.image_dir, exist_ok=True)
            success = download_media(file_token, local_path)
            if not success:
                return "[图片下载失败]"

        self.images_downloaded.append({
            "token": file_token,
            "path": os.path.join("images", filename),
            "width": width,
            "height": height,
            "source": "sheet_embed_image",
        })

        rel_path = os.path.join("images", filename)
        return f"![image]({rel_path})"

    def _render_quote(self, block, _depth=0):
        children_ids = block.get("children", [])
        for child_id in children_ids:
            child = self.block_dict.get(child_id)
            if child:
                text = get_block_text(child)
                if text:
                    self.lines.append(f"> {text}")
        self.lines.append("")

    def _render_board(self, block):
        """渲染画板：下载缩略图 + 提取文本"""
        board_data = block.get("board", {})
        board_id = board_data.get("token", "")
        if not board_id:
            return

        self.lines.append("**[画板]**")
        self.lines.append("")

        if not self.skip_images:
            filename = f"board_{board_id}.jpg"
            local_path = os.path.join(self.image_dir, filename)
            os.makedirs(self.image_dir, exist_ok=True)

            success = download_board_thumbnail(board_id, local_path)
            if success:
                self.images_downloaded.append({
                    "token": f"board_{board_id}",
                    "path": os.path.join("images", filename),
                    "type": "board_thumbnail",
                })
                rel_path = os.path.join("images", filename)
                self.lines.append(f"![board]({rel_path})")
                self.lines.append("")

        self._fetch_board_text(board_id)

    def _fetch_board_text(self, board_id):
        """获取画板中的文本节点"""
        try:
            result = feishu_api_get(
                f"/open-apis/board/v1/whiteboards/{board_id}/nodes"
            )
            nodes = result.get("data", {}).get("nodes", [])
            text_parts = []
            for node in nodes:
                if node.get("type") == "text_shape":
                    text_data = node.get("text", {})
                    text_content = text_data.get("text", "")
                    if text_content:
                        text_parts.append(text_content)

            if text_parts:
                self.lines.append("画板文本内容：")
                for part in text_parts:
                    for line in part.split("\n"):
                        if line.strip():
                            self.lines.append(f"- {line.strip()}")
                self.lines.append("")
        except Exception as e:
            log(f"获取画板文本失败: {e}")

    def _render_divider(self):
        self.lines.append("---")
        self.lines.append("")


# ==================== 单文档获取 ====================

def fetch_single_doc(document_id, image_dir, skip_images=False):
    """获取单个文档的 Markdown 内容和元数据。

    返回 (markdown_content, title, block_count, image_count, images_downloaded)
    """
    blocks = fetch_all_blocks(document_id)
    if not blocks:
        return "", "", 0, 0, []

    renderer = MarkdownRenderer(
        blocks,
        image_dir=image_dir,
        skip_images=skip_images,
    )
    markdown_content, title_from_blocks = renderer.render()
    return (
        markdown_content,
        title_from_blocks,
        len(blocks),
        len(renderer.images_downloaded),
        renderer.images_downloaded,
    )


# ==================== 主流程 ====================

def main():
    parser = argparse.ArgumentParser(
        description="获取飞书文档内容（文字+图片），输出 Markdown"
    )
    parser.add_argument(
        "--url",
        help="飞书文档 URL（wiki/docx/docs）",
    )
    parser.add_argument(
        "--doc-id",
        help="直接指定 document_id（与 --url 二选一）",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="图片输出目录（默认当前目录，图片保存到 {output-dir}/images/）",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="跳过图片下载，仅获取文字",
    )
    parser.add_argument(
        "--with-children",
        action="store_true",
        help="同时获取 wiki 子文档（仅对 wiki 链接生效）",
    )
    parser.add_argument(
        "--max-children",
        type=int,
        default=10,
        help="子文档获取上限（默认 10），达到后停止递归",
    )

    args = parser.parse_args()

    if not args.url and not args.doc_id:
        parser.error("必须指定 --url 或 --doc-id")

    image_dir = os.path.join(args.output_dir, "images")

    # 1. 解析 document_id
    document_id = None
    doc_title = ""
    wiki_info = None

    if args.doc_id:
        document_id = args.doc_id
        log(f"使用指定的 document_id: {document_id}")
    else:
        url = args.url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            log_error(f"--url 参数不是有效的 HTTP(S) 链接: {url!r}")
            sys.exit(1)
        doc_type, token = parse_document_url(url)
        log(f"从 URL 解析: type={doc_type}, token={token}")

        if doc_type == "wiki":
            document_id, doc_title, space_id, node_token, has_child = (
                resolve_wiki_to_docx_id(token)
            )
            wiki_info = {
                "space_id": space_id,
                "node_token": node_token,
                "has_child": has_child,
            }
            log(f"Wiki 解析为 document_id: {document_id}, 标题: {doc_title}, "
                f"has_child: {has_child}")
        else:
            document_id = token

    # 2. 获取主文档
    log(f"获取文档 blocks: {document_id}")
    markdown_content, title_from_blocks, main_block_count, main_img_count, main_images = (
        fetch_single_doc(document_id, image_dir, args.skip_images)
    )

    if not markdown_content.strip():
        log_error("文档没有内容")
        sys.exit(1)

    final_title = doc_title or title_from_blocks

    # 3. 输出主文档 Markdown 到 stdout
    if final_title:
        print(f"# {final_title}")
        print()
    print(markdown_content)

    # 4. 获取子文档（仅 wiki 且启用 --with-children）
    child_docs_meta = []
    skipped_meta = []
    truncated = False
    total_children_found = 0

    if (args.with_children
            and wiki_info
            and wiki_info["has_child"]
            and wiki_info["space_id"]):
        log(f"开始获取子文档 (max={args.max_children})...")
        fetched_nodes, skipped_nodes, truncated, total_children_found = (
            list_wiki_children(
                wiki_info["space_id"],
                wiki_info["node_token"],
                max_children=args.max_children,
            )
        )
        skipped_meta = skipped_nodes

        for idx, child_node in enumerate(fetched_nodes, start=1):
            child_filename = f"requirement_doc_sub_{idx}.md"
            child_path = os.path.join(args.output_dir, child_filename)
            child_obj_token = child_node["obj_token"]
            child_title = child_node["title"]

            log(f"获取子文档 {idx}/{len(fetched_nodes)}: {child_title}")
            try:
                child_md, child_title_blocks, _, child_img_count, _ = (
                    fetch_single_doc(child_obj_token, image_dir, args.skip_images)
                )
                effective_title = child_title or child_title_blocks
                with open(child_path, "w", encoding="utf-8") as f:
                    if effective_title:
                        f.write(f"# {effective_title}\n\n")
                    f.write(child_md)

                child_docs_meta.append({
                    "file": child_filename,
                    "title": effective_title,
                    "image_count": child_img_count,
                    "depth": child_node["depth"],
                })
            except Exception as e:
                log_error(f"获取子文档失败 ({child_title}): {e}")
                child_docs_meta.append({
                    "file": child_filename,
                    "title": child_title,
                    "image_count": 0,
                    "depth": child_node["depth"],
                    "error": str(e),
                })

        log(f"子文档获取完成: {len(child_docs_meta)} 篇"
            + (f"（截断，共发现 {total_children_found} 篇）" if truncated else ""))

    # 5. 输出元数据到 stderr
    metadata = {
        "title": final_title,
        "document_id": document_id,
        "total_blocks": main_block_count,
        "images": main_images,
        "image_count": main_img_count,
        "image_dir": os.path.relpath(image_dir, args.output_dir)
            if not args.skip_images else None,
    }

    if args.with_children:
        metadata["child_docs"] = child_docs_meta
        metadata["truncated"] = truncated
        metadata["total_children_found"] = total_children_found
        if skipped_meta:
            metadata["skipped"] = skipped_meta

    print(json.dumps(metadata, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
