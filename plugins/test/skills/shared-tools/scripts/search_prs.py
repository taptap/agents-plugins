#!/usr/bin/env python3
"""
搜索 Story/Bug 关联的 GitHub PR。

遍历配置的仓库，搜索标题/描述中包含 work_item_id 的 PR（open + merged），
输出按仓库分组的 PR 信息（JSON）。排除 closed-unmerged（被拒绝/废弃）的 PR。

用法:
    python3 search_prs.py <work_item_id>

环境变量:
    GITHUB_URL            - GitHub API 地址（默认 https://api.github.com）
    GITHUB_TOKEN          - GitHub Token（必填）
    GITHUB_REPO_MAPPING   - 仓库映射（JSON，key 为平台，value 为 repo 或 repo 列表）
                            示例: {"server": ["org/repo-a"], "web": "org/repo-b"}
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Dict, List, Optional, Set
from urllib.parse import urlencode

GITHUB_URL = os.environ.get("GITHUB_URL", "https://api.github.com").rstrip("/")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DEFAULT_REPO_MAPPING: Dict[str, List[str]] = {}


def _load_repo_mapping() -> Dict[str, List[str]]:
    """读取仓库映射并标准化为 list。"""
    raw = os.environ.get("GITHUB_REPO_MAPPING", "")
    if not raw:
        return dict(DEFAULT_REPO_MAPPING)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        print(f"[WARN] GITHUB_REPO_MAPPING 解析失败，已忽略: {exc}", file=sys.stderr)
        return dict(DEFAULT_REPO_MAPPING)

    normalized: Dict[str, List[str]] = {}
    for platform, repos in parsed.items():
        if isinstance(repos, str) and repos:
            normalized[str(platform)] = [repos]
        elif isinstance(repos, list):
            normalized[str(platform)] = [str(repo) for repo in repos if repo]
    return normalized


REPO_MAPPING = _load_repo_mapping()


def _api_get(path: str, params: Optional[dict] = None) -> dict:
    """调用 GitHub API。"""
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
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _search_repo_prs(repo: str, term: str, qualifier: str) -> List[dict]:
    """在单个 repo 内搜索 PR（支持分页）。"""
    query = f'repo:{repo} is:pr in:title,body "{term}" {qualifier}'
    all_items: List[dict] = []
    page = 1

    while True:
        result = _api_get("/search/issues", params={"q": query, "per_page": 100, "page": page})
        items = result.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1

    return all_items


def _contains_work_item(term: str, title: str, body: str) -> bool:
    """用词边界匹配，避免 '123' 匹配到 '12345' 的误报。"""
    import re
    text = f"{title} {body}"
    variants = [re.escape(term), re.escape(f"TAP-{term}"), re.escape(f"#{term}")]
    pattern = "|".join(variants)
    return bool(re.search(rf"(?i)(?<!\w)(?:{pattern})(?!\w)", text))


def _extract_repo_from_issue_url(html_url: str) -> str:
    # https://github.com/owner/repo/pull/123
    parts = html_url.split("/")
    if len(parts) < 6:
        return ""
    return f"{parts[3]}/{parts[4]}"


def search_related_prs(work_item_id: str) -> dict:
    seen_urls: Set[str] = set()
    prs_by_repo: Dict[str, List[dict]] = {}
    # 搜索已合并 + 进行中的 PR，排除 closed-unmerged（与 search_mrs.py 一致）
    search_qualifiers = ["is:open", "is:merged"]
    terms = [work_item_id, f"TAP-{work_item_id}", f"#{work_item_id}"]

    repos: List[str] = []
    for repo_list in REPO_MAPPING.values():
        repos.extend(repo_list)
    repos = sorted(set(repos))

    for repo in repos:
        collected: List[dict] = []
        for term in terms:
            for qualifier in search_qualifiers:
                try:
                    issues = _search_repo_prs(repo, term, qualifier)
                except Exception as exc:
                    print(f"[WARN] 搜索 PR 失败: repo={repo}, term={term}, qualifier={qualifier}, error={exc}", file=sys.stderr)
                    continue

                for issue in issues:
                    html_url = issue.get("html_url", "")
                    if not html_url or html_url in seen_urls:
                        continue
                    title = issue.get("title", "")
                    body = issue.get("body") or ""
                    if not _contains_work_item(work_item_id, title, body):
                        continue

                    seen_urls.add(html_url)
                    current_repo = _extract_repo_from_issue_url(html_url) or repo
                    collected.append({
                        "number": issue.get("number"),
                        "url": html_url,
                        "title": title,
                        "description": " ".join(body.split())[:200],
                        "state": issue.get("state", ""),
                        "author": (issue.get("user") or {}).get("login", ""),
                        "merged_at": (issue.get("pull_request") or {}).get("merged_at") or "",
                        "repo": current_repo,
                    })
        if collected:
            prs_by_repo[repo] = collected

    return {
        "work_item_id": work_item_id,
        "total_prs": len(seen_urls),
        "prs_by_repo": prs_by_repo,
        "all_pr_urls": sorted(seen_urls),
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 search_prs.py <work_item_id>", file=sys.stderr)
        sys.exit(1)

    if not GITHUB_TOKEN:
        print("[ERROR] 环境变量 GITHUB_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    if not REPO_MAPPING:
        print("[ERROR] 环境变量 GITHUB_REPO_MAPPING 未设置，无法确定搜索范围", file=sys.stderr)
        sys.exit(1)

    work_item_id = sys.argv[1]
    result = search_related_prs(work_item_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
