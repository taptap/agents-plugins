#!/usr/bin/env python3
"""
搜索 Story 关联的 GitLab MR

遍历所有代码仓库，搜索标题或描述中包含 story_id 的 MR（已合并 + 进行中），
输出按平台分组的 MR 信息（JSON 格式），包含 URL、标题、描述摘要和状态。

用法:
    python3 search_mrs.py <story_id>

环境变量:
    GITLAB_URL              - GitLab 实例地址（必填，无默认值）
    GITLAB_TOKEN            - GitLab Private Token（必填）
    GITLAB_SSL_VERIFY       - 设置为 false 可禁用 SSL 证书验证（默认启用验证）
    GITLAB_PROJECT_MAPPING  - 项目 ID 映射（JSON 格式，必填，value 为 int 项目 ID 或 ID 列表）
                              示例: '{"server": 2103, "android": 4252, "mini_game": [4191, 4218]}'
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import ssl
import sys
import urllib.request
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

# ==================== 配置 ====================

GITLAB_URL = os.environ.get("GITLAB_URL", "")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")


def _load_project_mapping() -> Dict[str, List[int]]:
    """
    从环境变量加载项目映射，未设置则返回空映射。
    支持两种 value 格式：int ID 或 int ID 列表。
    字符串值会被拒绝并报错（project path 格式不支持，必须使用 int ID）。
    """
    env_mapping = os.environ.get("GITLAB_PROJECT_MAPPING", "")
    if not env_mapping:
        return {}
    try:
        raw = json.loads(env_mapping)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  [WARN] GITLAB_PROJECT_MAPPING 解析失败: {e}", file=sys.stderr)
        return {}

    normalized: Dict[str, List[int]] = {}
    for platform, ids in raw.items():
        if isinstance(ids, int):
            normalized[str(platform)] = [ids]
        elif isinstance(ids, list):
            int_ids = []
            for v in ids:
                if isinstance(v, int):
                    int_ids.append(v)
                else:
                    print(f"  [WARN] GITLAB_PROJECT_MAPPING[{platform}] 中的值 {v!r} 不是 int，已跳过。"
                          f"请使用 GitLab 项目 ID（数字），而非 project path", file=sys.stderr)
            if int_ids:
                normalized[str(platform)] = int_ids
        else:
            print(f"  [WARN] GITLAB_PROJECT_MAPPING[{platform}] 的值 {ids!r} 类型不支持，已跳过。"
                  f"请使用 int 或 int 列表", file=sys.stderr)
    return normalized


PROJECT_ID_MAPPING: Dict[str, List[int]] = _load_project_mapping()

# 项目 ID -> 项目路径映射（用于构造 MR URL）
# 如果缓存未命中，会通过 API 查询
_project_path_cache: Dict[int, str] = {}

# SSL 上下文（复用）
# 设置 GITLAB_SSL_VERIFY=false 可禁用证书验证（内网自签名证书场景）
_ssl_ctx = ssl.create_default_context()
if os.environ.get("GITLAB_SSL_VERIFY", "").lower() in ("false", "0", "no"):
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE

# 描述摘要最大长度
DESC_MAX_LEN = 200


# ==================== GitLab API 调用 ====================

def _api_get(path: str, params: Optional[dict] = None) -> Union[list, dict]:
    """调用 GitLab REST API（GET 请求），使用 stdlib urllib"""
    url = f"{GITLAB_URL}/api/v4{path}"
    if params:
        url += "?" + urlencode(params)

    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": GITLAB_TOKEN})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_project_path(project_id: int) -> str:
    """获取项目的 path_with_namespace（带缓存）"""
    if project_id in _project_path_cache:
        return _project_path_cache[project_id]

    try:
        project = _api_get(f"/projects/{project_id}")
        path = project.get("path_with_namespace", "")
        _project_path_cache[project_id] = path
        return path
    except Exception as e:
        print(f"  [WARN] 获取项目 {project_id} 信息失败: {e}", file=sys.stderr)
        return ""


def _search_mrs_in_project(
        project_id: int,
        search_term: str,
        state: str = "merged",
) -> List[dict]:
    """在指定项目中搜索指定状态的 MR（支持自动分页）"""
    all_mrs: List[dict] = []
    page = 1

    while True:
        try:
            mrs = _api_get(
                f"/projects/{project_id}/merge_requests",
                params={
                    "search": search_term,
                    "in": "title,description",
                    "state": state,
                    "per_page": 100,
                    "page": page,
                },
            )
            if not isinstance(mrs, list) or len(mrs) == 0:
                break
            all_mrs.extend(mrs)
            # 不满一页说明已到最后
            if len(mrs) < 100:
                break
            page += 1
        except Exception as e:
            print(
                f"  [WARN] 搜索 MR 失败 (project={project_id}, search={search_term}, page={page}): {e}",
                file=sys.stderr,
            )
            break

    return all_mrs


def _truncate(text: str, max_len: int) -> str:
    """截断文本，保留完整单词/句子"""
    if not text:
        return ""
    # 去除多余空白
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def _verify_story_id_in_mr(story_id: str, title: str, description: str) -> bool:
    """
    二次验证：确认 story_id 确实出现在 MR 的标题或描述中。
    GitLab search API 可能返回部分匹配的结果，此函数用词边界做精确校验，
    避免 "123" 匹配到 "12345" 的误报。
    """
    import re
    text = f"{title} {description}"
    # 使用词边界 \b 避免子串误匹配（如 123 匹配到 12345）
    variants = [re.escape(story_id), re.escape(f"TAP-{story_id}"), re.escape(f"#{story_id}")]
    pattern = "|".join(variants)
    return bool(re.search(rf"(?i)(?<!\w)(?:{pattern})(?!\w)", text))


# ==================== 核心逻辑 ====================

def search_story_mrs(story_id: str) -> dict:
    """
    搜索 Story 关联的所有 MR（已合并 + 进行中，排除已关闭）

    Args:
        story_id: 飞书需求 ID

    Returns:
        dict 包含按平台分组的 MR 详细信息
    """
    # 搜索关键词（与参考代码一致）
    search_terms = [
        story_id,
        f"TAP-{story_id}",
        f"#{story_id}",
    ]

    # 搜索的 MR 状态：merged（已合并）+ opened（进行中），排除 closed
    search_states = ["merged", "opened"]

    seen_urls: set = set()
    mrs_by_platform: Dict[str, List[dict]] = {}

    for platform, project_ids in PROJECT_ID_MAPPING.items():
        platform_mrs: List[dict] = []

        for project_id in project_ids:
            print(f"  搜索 {platform} (project_id={project_id}) ...", file=sys.stderr)

            project_path = _get_project_path(project_id)
            if not project_path:
                continue

            for search_term in search_terms:
                for state in search_states:
                    mrs = _search_mrs_in_project(project_id, search_term, state=state)

                    for mr in mrs:
                        mr_iid = mr.get("iid")
                        mr_url = f"{GITLAB_URL}/{project_path}/-/merge_requests/{mr_iid}"

                        if mr_url in seen_urls:
                            continue

                        # 二次验证：确认 story_id 确实出现在标题或描述中
                        mr_title = mr.get("title", "")
                        mr_full_desc = mr.get("description") or ""
                        if not _verify_story_id_in_mr(story_id, mr_title, mr_full_desc):
                            continue

                        seen_urls.add(mr_url)

                        mr_desc = _truncate(mr_full_desc, DESC_MAX_LEN)
                        mr_state = mr.get("state", "")

                        platform_mrs.append({
                            "iid": mr_iid,
                            "url": mr_url,
                            "title": mr_title,
                            "description": mr_desc,
                            "state": mr_state,
                            "author": mr.get("author", {}).get("username", ""),
                            "merged_at": mr.get("merged_at", ""),
                            "project_path": project_path,
                        })
                        print(
                            f"    找到 MR: !{mr_iid} [{mr_state}] - {mr_title[:60]}",
                            file=sys.stderr,
                        )

        if platform_mrs:
            mrs_by_platform[platform] = platform_mrs

    # 构建扁平 URL 列表（兼容旧格式）
    all_mr_urls = sorted(seen_urls)

    return {
        "story_id": story_id,
        "total_mrs": len(seen_urls),
        "mrs_by_platform": mrs_by_platform,
        "all_mr_urls": all_mr_urls,
    }


# ==================== 入口 ====================

def main():
    if len(sys.argv) < 2:
        print("用法: python3 search_mrs.py <story_id>", file=sys.stderr)
        sys.exit(1)

    story_id = sys.argv[1]

    if not GITLAB_URL:
        print("[ERROR] 环境变量 GITLAB_URL 未设置", file=sys.stderr)
        sys.exit(1)

    if not GITLAB_TOKEN:
        print("[ERROR] 环境变量 GITLAB_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    if not PROJECT_ID_MAPPING:
        print("[ERROR] 环境变量 GITLAB_PROJECT_MAPPING 未设置，无法确定搜索范围", file=sys.stderr)
        sys.exit(1)

    print(f"搜索 Story {story_id} 关联的 MR（merged + opened）...", file=sys.stderr)
    result = search_story_mrs(story_id)
    print(f"搜索完成: 共找到 {result['total_mrs']} 个 MR", file=sys.stderr)

    # JSON 输出到 stdout（供 AI 解析）
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
