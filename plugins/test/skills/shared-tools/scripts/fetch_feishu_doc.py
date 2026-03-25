#!/usr/bin/env python3
"""
飞书文档获取工具 — 供 AI Agent 在数据获取阶段使用

获取飞书文档（wiki/docx/docs）的完整内容并转换为 Markdown 格式。

用法:
    python3 fetch_feishu_doc.py --url "https://xxx.feishu.cn/wiki/AbCdEfG" --output-dir .
    python3 fetch_feishu_doc.py --doc-id "AbCdEfG" --output-dir .
    python3 fetch_feishu_doc.py --url "..." --output-dir . --skip-images

输出:
    stdout: Markdown 格式文档内容
    stderr: JSON 元数据 {"title": "...", "document_id": "...", "images": [...], "image_count": N}

环境变量:
    FEISHU_APP_ID     - 飞书应用 App ID
    FEISHU_APP_SECRET - 飞书应用 App Secret
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
import time
from typing import Optional
from urllib.parse import urlencode, urlparse

# ==================== 配置 ====================

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_HOST = os.environ.get("FEISHU_HOST", "https://open.feishu.cn")

_tenant_token_cache: Optional[str] = None
_tenant_token_expiry: float = 0  # Unix timestamp


# ==================== 飞书 API ====================

def _get_tenant_access_token() -> str:
    global _tenant_token_cache, _tenant_token_expiry
    if _tenant_token_cache and time.time() < _tenant_token_expiry:
        return _tenant_token_cache

    url = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
    payload = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {data.get('msg')}")

    _tenant_token_cache = data["tenant_access_token"]
    # 飞书 token 有效期 2 小时，提前 5 分钟刷新
    _tenant_token_expiry = time.time() + data.get("expire", 7200) - 300
    return _tenant_token_cache


def _api_get(path: str, params: Optional[dict] = None):
    token = _get_tenant_access_token()
    url = f"{FEISHU_HOST}/open-apis{path}"
    if params:
        url += "?" + urlencode(params)

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_image(file_token: str, output_path: str):
    token = _get_tenant_access_token()
    url = f"{FEISHU_HOST}/open-apis/drive/v1/medias/{file_token}/download"

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())


# ==================== URL 解析 ====================

def _parse_url(url: str) -> tuple:
    """
    解析飞书文档 URL，返回 (doc_type, token)。

    支持的 URL 格式:
      - https://xxx.feishu.cn/wiki/AbCdEfG
      - https://xxx.feishu.cn/docx/AbCdEfG
      - https://xxx.feishu.cn/docs/AbCdEfG
      - https://xxx.larkoffice.com/wiki/AbCdEfG
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) < 2:
        raise ValueError(f"无法解析 URL: {url}")

    doc_type = path_parts[0]  # wiki / docx / docs
    token = path_parts[1]

    if doc_type not in ("wiki", "docx", "docs"):
        raise ValueError(f"不支持的文档类型: {doc_type} (URL: {url})")

    return doc_type, token


def _resolve_wiki_to_docx(wiki_token: str) -> str:
    """将 wiki token 解析为实际的 document_id"""
    resp = _api_get("/wiki/v2/spaces/get_node", {"token": wiki_token})
    if resp.get("code") != 0:
        raise RuntimeError(f"获取 wiki 节点失败: {resp.get('msg')}")

    node = resp.get("data", {}).get("node", {})
    obj_token = node.get("obj_token", "")
    if not obj_token:
        raise RuntimeError(f"wiki 节点无 obj_token: {wiki_token}")

    return obj_token


# ==================== 文档获取与转换 ====================

def _get_document_blocks(document_id: str) -> list:
    """获取文档所有 block，自动处理分页"""
    all_blocks = []
    page_token = None

    while True:
        params = {"document_id": document_id, "page_size": "500"}
        if page_token:
            params["page_token"] = page_token

        resp = _api_get(f"/docx/v1/documents/{document_id}/blocks", params)
        if resp.get("code") != 0:
            raise RuntimeError(f"获取文档 blocks 失败: {resp.get('msg')}")

        items = resp.get("data", {}).get("items", [])
        all_blocks.extend(items)

        if not resp.get("data", {}).get("has_more", False):
            break
        page_token = resp["data"].get("page_token")

    return all_blocks


def _get_document_title(document_id: str) -> str:
    resp = _api_get(f"/docx/v1/documents/{document_id}")
    if resp.get("code") != 0:
        return ""
    return resp.get("data", {}).get("document", {}).get("title", "")


def _extract_text(text_elements: list) -> str:
    """从 text_run / mention 等元素中提取纯文本"""
    parts = []
    for elem in text_elements:
        if "text_run" in elem:
            content = elem["text_run"].get("content", "")
            style = elem["text_run"].get("text_element_style", {})
            if style.get("bold"):
                content = f"**{content}**"
            if style.get("italic"):
                content = f"*{content}*"
            if style.get("strikethrough"):
                content = f"~~{content}~~"
            if style.get("inline_code"):
                content = f"`{content}`"
            link = style.get("link", {})
            if link.get("url"):
                content = f"[{content}]({link['url']})"
            parts.append(content)
        elif "mention_user" in elem:
            parts.append(f"@{elem['mention_user'].get('user_id', '?')}")
        elif "mention_doc" in elem:
            parts.append(elem["mention_doc"].get("title", "[文档]"))
    return "".join(parts)


def _blocks_to_markdown(blocks: list) -> tuple:
    """
    将飞书文档 blocks 转换为 Markdown。
    返回 (markdown_text, image_tokens)。
    """
    lines = []
    image_tokens = []

    for block in blocks:
        block_type = block.get("block_type")

        # 页面 block（根节点），跳过
        if block_type == 1:
            continue

        # 文本
        if block_type == 2:
            text = block.get("text", {})
            elements = text.get("elements", [])
            lines.append(_extract_text(elements))

        # 标题 (heading1=3, heading2=4, ..., heading9=11)
        elif block_type in range(3, 12):
            level = block_type - 2
            heading = block.get(f"heading{level}", {})
            elements = heading.get("elements", [])
            lines.append(f"{'#' * level} {_extract_text(elements)}")

        # 无序列表
        elif block_type == 12:
            bullet = block.get("bullet", {})
            elements = bullet.get("elements", [])
            lines.append(f"- {_extract_text(elements)}")

        # 有序列表
        elif block_type == 13:
            ordered = block.get("ordered", {})
            elements = ordered.get("elements", [])
            lines.append(f"1. {_extract_text(elements)}")

        # 代码块
        elif block_type == 14:
            code = block.get("code", {})
            elements = code.get("elements", [])
            lang = code.get("style", {}).get("language", "")
            lang_map = {1: "python", 2: "java", 3: "javascript", 4: "go",
                        5: "c", 6: "cpp", 7: "csharp", 8: "ruby", 9: "swift",
                        10: "kotlin", 12: "typescript", 14: "shell", 15: "rust",
                        16: "sql", 20: "json", 22: "yaml", 25: "html", 26: "css"}
            lang_str = lang_map.get(lang, "")
            text = _extract_text(elements)
            lines.append(f"```{lang_str}\n{text}\n```")

        # 引用
        elif block_type == 15:
            quote = block.get("quote", {})
            elements = quote.get("elements", [])
            lines.append(f"> {_extract_text(elements)}")

        # 待办事项
        elif block_type == 17:
            todo = block.get("todo", {})
            elements = todo.get("elements", [])
            done = todo.get("style", {}).get("done", False)
            mark = "x" if done else " "
            lines.append(f"- [{mark}] {_extract_text(elements)}")

        # 分割线
        elif block_type == 22:
            lines.append("---")

        # 图片
        elif block_type == 27:
            image = block.get("image", {})
            file_token = image.get("token", "")
            if file_token:
                image_tokens.append(file_token)
                # 使用 sanitized name 保持与文件保存时一致
                safe_token = file_token.replace("/", "_").replace("..", "_")
                lines.append(f"![image](images/{safe_token}.png)")

        # 表格（简化处理：内容未提取，仅占位标记）
        elif block_type == 18:
            lines.append("[表格 — 内容未提取，请查看原文档]")

        # 其他 block 类型：尝试提取 elements
        else:
            for key in block:
                if isinstance(block[key], dict) and "elements" in block[key]:
                    text = _extract_text(block[key]["elements"])
                    if text.strip():
                        lines.append(text)
                    break

    markdown = "\n\n".join(lines)
    # 清理连续空行
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown, image_tokens


# ==================== 主流程 ====================

def fetch_document(url: Optional[str] = None, doc_id: Optional[str] = None,
                   output_dir: str = ".", skip_images: bool = False):
    """
    获取飞书文档并输出 Markdown。

    Args:
        url: 飞书文档 URL
        doc_id: 文档 ID（与 url 二选一）
        output_dir: 输出目录（图片下载位置）
        skip_images: 跳过图片下载
    """
    document_id = doc_id

    if url:
        doc_type, token = _parse_url(url)
        if doc_type == "wiki":
            document_id = _resolve_wiki_to_docx(token)
        else:
            document_id = token

    if not document_id:
        raise ValueError("必须提供 --url 或 --doc-id")

    title = _get_document_title(document_id)
    blocks = _get_document_blocks(document_id)
    markdown, image_tokens = _blocks_to_markdown(blocks)

    if title:
        markdown = f"# {title}\n\n{markdown}"

    downloaded_images = []
    warnings = []
    if image_tokens and not skip_images:
        images_dir = Path(output_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for token in image_tokens:
            # 防止路径穿越：拒绝含 / 或 .. 的 token
            safe_name = token.replace("/", "_").replace("..", "_")
            img_path = images_dir / f"{safe_name}.png"
            # 二次验证：确保最终路径仍在 images_dir 内
            if not str(img_path.resolve()).startswith(str(images_dir.resolve())):
                warnings.append(f"图片 token 路径不安全，已跳过: {token}")
                continue
            try:
                _download_image(token, str(img_path))
                downloaded_images.append(str(img_path))
            except Exception as e:
                warnings.append(f"图片下载失败 {token}: {e}")

    # stdout: Markdown 内容
    print(markdown)

    # stderr: JSON 元数据（保持为合法 JSON，警告信息合并到 warnings 字段）
    meta = {
        "title": title,
        "document_id": document_id,
        "images": downloaded_images,
        "image_count": len(image_tokens),
        "warnings": warnings,
    }
    print(json.dumps(meta, ensure_ascii=False), file=sys.stderr)


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="获取飞书文档并转换为 Markdown",
    )
    parser.add_argument("--url", help="飞书文档 URL（wiki/docx/docs）")
    parser.add_argument("--doc-id", help="文档 ID（与 --url 二选一）")
    parser.add_argument("--output-dir", default=".", help="输出目录（默认当前目录）")
    parser.add_argument("--skip-images", action="store_true", help="跳过图片下载")

    args = parser.parse_args()

    if not args.url and not args.doc_id:
        parser.error("必须提供 --url 或 --doc-id")

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("[ERROR] 环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET 未设置",
              file=sys.stderr)
        sys.exit(1)

    try:
        fetch_document(
            url=args.url,
            doc_id=args.doc_id,
            output_dir=args.output_dir,
            skip_images=args.skip_images,
        )
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"[ERROR] 飞书 API 返回 {e.code}: {e.reason}", file=sys.stderr)
        if body:
            print(f"  响应: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
