#!/usr/bin/env python3
"""
GitLab 辅助工具 — 供 AI Agent 在变更分析流程中使用

提供三个子命令：
  mr-diff       获取 MR 的代码变更 diff
  mr-detail     获取 MR 完整详情
  file-content  获取仓库中指定文件的内容

用法:
    python3 gitlab_helper.py mr-diff   <project_path> <mr_iid>
    python3 gitlab_helper.py mr-detail <project_path> <mr_iid>
    python3 gitlab_helper.py file-content <project_path> <file_path> [--ref main]

环境变量:
    GITLAB_URL        - GitLab 实例地址（必填，无默认值）
    GITLAB_TOKEN      - GitLab Private Token
    GITLAB_SSL_VERIFY - 设置为 false 可禁用 SSL 证书验证（默认启用验证）
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.request
from typing import Optional, Union
from urllib.parse import urlencode, quote

# ==================== 配置 ====================

GITLAB_URL = os.environ.get("GITLAB_URL", "")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")

# SSL 上下文（复用）
# 设置 GITLAB_SSL_VERIFY=false 可禁用证书验证（内网自签名证书场景）
_ssl_ctx = ssl.create_default_context()
if os.environ.get("GITLAB_SSL_VERIFY", "").lower() in ("false", "0", "no"):
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE


# ==================== GitLab API ====================

def _api_get(path: str, params: Optional[dict] = None, raw: bool = False):
    """
    调用 GitLab REST API（GET）

    Args:
        path: API 路径（如 /projects/123/merge_requests/1）
        params: 查询参数
        raw: True 时返回原始字节（用于文件内容），False 时解析 JSON
    """
    url = f"{GITLAB_URL}/api/v4{path}"
    if params:
        url += "?" + urlencode(params)

    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": GITLAB_TOKEN})
    with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as resp:
        data = resp.read()
        if raw:
            return data.decode("utf-8")
        return json.loads(data.decode("utf-8"))


def _resolve_project_id(project_path: str) -> int:
    """将 project_path（如 server/zeus）解析为 project_id"""
    encoded = quote(project_path, safe="")
    project = _api_get(f"/projects/{encoded}")
    return project["id"]


# ==================== 子命令实现 ====================

def cmd_mr_diff(project_path: str, mr_iid: str):
    """
    获取 MR 的代码变更 diff

    输出格式：对每个变更文件打印 unified diff
    """
    project_id = _resolve_project_id(project_path)

    # 获取 MR changes（含每个文件的 diff）
    data = _api_get(
        f"/projects/{project_id}/merge_requests/{mr_iid}/changes",
        params={"access_raw_diffs": "true"},
    )

    title = data.get("title", "")
    state = data.get("state", "")
    changes = data.get("changes", [])

    print(f"MR !{mr_iid}: {title} [{state}]", file=sys.stderr)
    print(f"变更文件数: {len(changes)}", file=sys.stderr)

    # 输出每个文件的 diff
    for change in changes:
        old_path = change.get("old_path", "")
        new_path = change.get("new_path", "")
        new_file = change.get("new_file", False)
        deleted_file = change.get("deleted_file", False)
        renamed_file = change.get("renamed_file", False)
        diff_text = change.get("diff", "")

        # 文件头
        if deleted_file:
            print(f"\n--- a/{old_path} (deleted)")
        elif new_file:
            print(f"\n+++ b/{new_path} (new file)")
        elif renamed_file:
            print(f"\n--- a/{old_path} → b/{new_path} (renamed)")
        else:
            print(f"\n--- a/{old_path}")
            print(f"+++ b/{new_path}")

        # diff 内容
        if diff_text:
            print(diff_text)
        else:
            print("  (binary file or no diff available)")


def cmd_mr_detail(project_path: str, mr_iid: str):
    """
    获取 MR 完整详情

    输出 JSON 格式，包含标题、完整描述、标签、变更文件列表等
    """
    project_id = _resolve_project_id(project_path)

    # 获取 MR 基本信息
    mr = _api_get(f"/projects/{project_id}/merge_requests/{mr_iid}")

    # 获取变更文件列表（不含完整 diff，只要文件名）
    changes_data = _api_get(
        f"/projects/{project_id}/merge_requests/{mr_iid}/changes",
    )
    changed_files = []
    for c in changes_data.get("changes", []):
        changed_files.append({
            "old_path": c.get("old_path"),
            "new_path": c.get("new_path"),
            "new_file": c.get("new_file", False),
            "deleted_file": c.get("deleted_file", False),
            "renamed_file": c.get("renamed_file", False),
        })

    result = {
        "iid": mr.get("iid"),
        "title": mr.get("title", ""),
        "description": mr.get("description", ""),
        "state": mr.get("state", ""),
        "author": mr.get("author", {}).get("username", ""),
        "merged_by": (mr.get("merged_by") or {}).get("username", ""),
        "merged_at": mr.get("merged_at", ""),
        "created_at": mr.get("created_at", ""),
        "source_branch": mr.get("source_branch", ""),
        "target_branch": mr.get("target_branch", ""),
        "labels": mr.get("labels", []),
        "web_url": mr.get("web_url", ""),
        "diff_stats": {
            "changed_files_count": mr.get("changes_count", ""),
        },
        "changed_files_count": len(changed_files),
        "changed_files": changed_files,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"MR !{mr_iid}: {len(changed_files)} 个变更文件", file=sys.stderr)


def cmd_file_content(project_path: str, file_path: str, ref: str = "main"):
    """
    获取仓库中指定文件的完整内容

    直接输出文件原始内容到 stdout
    """
    project_id = _resolve_project_id(project_path)

    # file_path 需要 URL 编码
    encoded_file = quote(file_path, safe="")

    content = _api_get(
        f"/projects/{project_id}/repository/files/{encoded_file}/raw",
        params={"ref": ref},
        raw=True,
    )

    print(content)
    print(f"文件: {file_path} (ref={ref}, {len(content)} bytes)", file=sys.stderr)


# ==================== 入口 ====================

USAGE = """\
用法:
    python3 gitlab_helper.py mr-diff      <project_path> <mr_iid>
    python3 gitlab_helper.py mr-detail    <project_path> <mr_iid>
    python3 gitlab_helper.py file-content <project_path> <file_path> [--ref main]

示例:
    python3 gitlab_helper.py mr-diff server/zeus 4521
    python3 gitlab_helper.py mr-detail server/zeus 4521
    python3 gitlab_helper.py file-content server/zeus src/main/java/App.java --ref main
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    if not GITLAB_URL:
        print("[ERROR] 环境变量 GITLAB_URL 未设置", file=sys.stderr)
        sys.exit(1)

    if not GITLAB_TOKEN:
        print("[ERROR] 环境变量 GITLAB_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "mr-diff":
            if len(sys.argv) < 4:
                print("用法: gitlab_helper.py mr-diff <project_path> <mr_iid>", file=sys.stderr)
                sys.exit(1)
            cmd_mr_diff(sys.argv[2], sys.argv[3])

        elif command == "mr-detail":
            if len(sys.argv) < 4:
                print("用法: gitlab_helper.py mr-detail <project_path> <mr_iid>", file=sys.stderr)
                sys.exit(1)
            cmd_mr_detail(sys.argv[2], sys.argv[3])

        elif command == "file-content":
            if len(sys.argv) < 4:
                print("用法: gitlab_helper.py file-content <project_path> <file_path> [--ref branch]", file=sys.stderr)
                sys.exit(1)
            ref = "main"
            # 解析 --ref 参数
            for i, arg in enumerate(sys.argv[4:], start=4):
                if arg == "--ref" and i + 1 < len(sys.argv):
                    ref = sys.argv[i + 1]
                    break
            cmd_file_content(sys.argv[2], sys.argv[3], ref)

        else:
            print(f"未知子命令: {command}\n", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            sys.exit(1)

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"[ERROR] GitLab API 返回 {e.code}: {e.reason}", file=sys.stderr)
        if body:
            print(f"  响应: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
