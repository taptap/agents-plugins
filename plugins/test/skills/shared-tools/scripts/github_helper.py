#!/usr/bin/env python3
"""
GitHub 辅助工具 — 供 AI Agent 在变更分析流程中使用。

提供三个子命令：
  pr-diff       获取 PR 的代码变更 diff
  pr-detail     获取 PR 完整详情
  file-content  获取仓库中指定文件内容

用法:
    python3 github_helper.py pr-diff <owner/repo> <pr_number>
    python3 github_helper.py pr-detail <owner/repo> <pr_number>
    python3 github_helper.py file-content <owner/repo> <file_path> [--ref main]

环境变量:
    GITHUB_URL    - GitHub API 地址（默认 https://api.github.com）
    GITHUB_TOKEN  - GitHub Token
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import urllib.request
from typing import Optional, Union
from urllib.parse import urlencode, quote

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

GITHUB_URL = os.environ.get("GITHUB_URL", "https://api.github.com").rstrip("/")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _api_get(path: str, params: Optional[dict] = None) -> Union[dict, list]:
    url = f"{GITHUB_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_pr_files(repo: str, pr_number: str) -> list:
    """获取 PR 的所有变更文件（支持分页）。"""
    all_files: list = []
    page = 1
    while True:
        files = _api_get(f"/repos/{repo}/pulls/{pr_number}/files",
                         params={"per_page": 100, "page": page})
        if not isinstance(files, list) or len(files) == 0:
            break
        all_files.extend(files)
        if len(files) < 100:
            break
        page += 1
    return all_files


def cmd_pr_diff(repo: str, pr_number: str):
    """输出 PR diff。"""
    files = _get_pr_files(repo, pr_number)
    for change in files:
        filename = change.get("filename", "")
        status = change.get("status", "")
        patch = change.get("patch") or ""
        print(f"\n--- {filename} [{status}]")
        if patch:
            print(patch)
        else:
            print("  (binary file or no patch)")


def cmd_pr_detail(repo: str, pr_number: str):
    """输出 PR 详情 JSON。"""
    pr = _api_get(f"/repos/{repo}/pulls/{pr_number}")
    files = _get_pr_files(repo, pr_number)

    changed_files = []
    for item in files:
        changed_files.append({
            "filename": item.get("filename", ""),
            "status": item.get("status", ""),
            "additions": item.get("additions", 0),
            "deletions": item.get("deletions", 0),
            "changes": item.get("changes", 0),
        })

    result = {
        "number": pr.get("number"),
        "title": pr.get("title", ""),
        "description": pr.get("body") or "",
        "state": pr.get("state", ""),
        "author": (pr.get("user") or {}).get("login", ""),
        "merged_by": (pr.get("merged_by") or {}).get("login", ""),
        "merged_at": pr.get("merged_at", ""),
        "created_at": pr.get("created_at", ""),
        "head_ref": ((pr.get("head") or {}).get("ref", "")),
        "base_ref": ((pr.get("base") or {}).get("ref", "")),
        "labels": [label.get("name", "") for label in pr.get("labels", [])],
        "web_url": pr.get("html_url", ""),
        "changed_files_count": len(changed_files),
        "changed_files": changed_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_file_content(repo: str, file_path: str, ref: str):
    """输出文件内容。"""
    encoded_path = quote(file_path, safe="")
    payload = _api_get(f"/repos/{repo}/contents/{encoded_path}", params={"ref": ref})
    if not isinstance(payload, dict):
        raise ValueError("GitHub API 返回异常，未获取到文件内容")
    encoded = payload.get("content", "")
    if not encoded:
        raise ValueError("文件内容为空")
    content = base64.b64decode(encoded).decode("utf-8", errors="replace")
    print(content)


USAGE = """\
用法:
    python3 github_helper.py pr-diff <owner/repo> <pr_number>
    python3 github_helper.py pr-detail <owner/repo> <pr_number>
    python3 github_helper.py file-content <owner/repo> <file_path> [--ref main]
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    if not GITHUB_TOKEN:
        print("[ERROR] 环境变量 GITHUB_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    try:
        if command == "pr-diff":
            if len(sys.argv) < 4:
                print("用法: github_helper.py pr-diff <owner/repo> <pr_number>", file=sys.stderr)
                sys.exit(1)
            cmd_pr_diff(sys.argv[2], sys.argv[3])
        elif command == "pr-detail":
            if len(sys.argv) < 4:
                print("用法: github_helper.py pr-detail <owner/repo> <pr_number>", file=sys.stderr)
                sys.exit(1)
            cmd_pr_detail(sys.argv[2], sys.argv[3])
        elif command == "file-content":
            if len(sys.argv) < 4:
                print("用法: github_helper.py file-content <owner/repo> <file_path> [--ref main]", file=sys.stderr)
                sys.exit(1)
            ref = "main"
            for index, arg in enumerate(sys.argv[4:], start=4):
                if arg == "--ref" and index + 1 < len(sys.argv):
                    ref = sys.argv[index + 1]
                    break
            cmd_file_content(sys.argv[2], sys.argv[3], ref)
        else:
            print(f"未知子命令: {command}", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            sys.exit(1)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"[ERROR] GitHub API 返回 {e.code}: {e.reason}", file=sys.stderr)
        if body:
            print(f"  响应: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
