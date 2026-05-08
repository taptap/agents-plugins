#!/usr/bin/env python3
"""校验所有 skill 的 contract.yaml 一致性。

检查项:
1. from_upstream 引用的文件名在上游 skill 的 output.files 中存在
2. 跨 skill 输出文件名无冲突（同名文件由不同 skill 产出）
3. contract.yaml 的 name 字段与目录名一致

可选参数:
  --allowlist <path>   YAML 白名单文件，用于豁免"经设计认可的冲突"。
                       格式见 plugins/test/contracts/known-collisions.yaml。
                       未列入白名单的冲突仍报 fail。
"""

import argparse
import os
import sys

try:
    import yaml
except ImportError:
    print("错误: 需要 pyyaml 库。请运行 pip install pyyaml")
    sys.exit(1)


def find_skills_dir():
    """定位 skills 目录。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.dirname(os.path.dirname(script_dir))
    if os.path.isdir(skills_dir):
        return skills_dir
    print(f"错误: 找不到 skills 目录: {skills_dir}")
    sys.exit(1)


def load_contracts(skills_dir):
    """加载所有 skill 的 contract.yaml。"""
    contracts = {}
    for entry in sorted(os.listdir(skills_dir)):
        contract_path = os.path.join(skills_dir, entry, "contract.yaml")
        if os.path.isfile(contract_path):
            with open(contract_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                contracts[entry] = data
    return contracts


def get_output_files(contract):
    """提取 skill 的输出文件名列表。"""
    output = contract.get("output", {})
    files = output.get("files", [])
    return [f["name"] for f in files if isinstance(f, dict) and "name" in f]


def get_upstream_refs(contract):
    """提取 skill 的 from_upstream 引用。"""
    refs = []
    for section_key in ("one_of", "any_of", "optional"):
        section = contract.get("input", {}).get(section_key, {})
        if not isinstance(section, dict):
            continue
        for param_name, param_def in section.items():
            if isinstance(param_def, dict) and "from_upstream" in param_def:
                upstream = param_def["from_upstream"]
                if isinstance(upstream, list):
                    for u in upstream:
                        refs.append((param_name, u))
                else:
                    refs.append((param_name, upstream))
    return refs


def check_name_consistency(contracts):
    """检查 contract.yaml 的 name 字段是否与目录名一致。"""
    issues = []
    for dir_name, contract in contracts.items():
        contract_name = contract.get("name", "")
        if contract_name != dir_name:
            issues.append(
                f"  [NAME] {dir_name}/contract.yaml: name='{contract_name}' != 目录名'{dir_name}'"
            )
    return issues


def load_allowlist(path):
    """加载白名单。返回 {filename: set(owners)} — 命中且 owners 子集即豁免。"""
    if not path:
        return {}
    if not os.path.isfile(path):
        print(f"警告: 白名单文件不存在: {path}", file=sys.stderr)
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    allowlist = {}
    for fname, entry in (data.get("collisions") or {}).items():
        owners = entry.get("owners") if isinstance(entry, dict) else None
        if owners:
            allowlist[fname] = set(owners)
    return allowlist


def check_output_collisions(contracts, allowlist=None):
    """检查跨 skill 的输出文件名冲突。allowlist 内的冲突降级为 warning。"""
    allowlist = allowlist or {}
    file_owners = {}
    for skill_name, contract in contracts.items():
        for fname in get_output_files(contract):
            file_owners.setdefault(fname, []).append(skill_name)

    issues = []
    warnings = []
    for fname, owners in sorted(file_owners.items()):
        if len(owners) <= 1:
            continue
        owners_set = set(owners)
        allowed_owners = allowlist.get(fname)
        if allowed_owners and owners_set.issubset(allowed_owners):
            warnings.append(
                f"  [ALLOWED] '{fname}' 共享 owner: {', '.join(sorted(owners_set))}（白名单豁免）"
            )
            continue
        # 部分新增 owner 不在白名单 → 仍报 fail，提示需补
        if allowed_owners:
            extra = sorted(owners_set - allowed_owners)
            issues.append(
                f"  [COLLISION] '{fname}' 出现新 owner {extra} 未列入白名单（已知 owners: {sorted(allowed_owners)}）"
            )
        else:
            issues.append(
                f"  [COLLISION] '{fname}' 被多个 skill 产出: {', '.join(owners)}"
            )
    return issues, warnings


def check_upstream_refs(contracts):
    """检查 from_upstream 引用是否有效。"""
    issues = []
    for skill_name, contract in contracts.items():
        for _param_name, upstream_skill in get_upstream_refs(contract):
            if upstream_skill not in contracts:
                issues.append(
                    f"  [MISSING] {skill_name}: from_upstream='{upstream_skill}' 不存在"
                )
    return issues


def main():
    parser = argparse.ArgumentParser(
        description="校验所有 skill 的 contract.yaml 一致性"
    )
    parser.add_argument(
        "--allowlist",
        default=None,
        help="YAML 白名单文件路径，豁免设计认可的 output collision",
    )
    args = parser.parse_args()

    skills_dir = find_skills_dir()
    contracts = load_contracts(skills_dir)
    allowlist = load_allowlist(args.allowlist)

    print(f"已加载 {len(contracts)} 个 skill 的 contract.yaml")
    if allowlist:
        print(f"已加载 {len(allowlist)} 条 collision 白名单")
    print()

    all_issues = []

    # 检查 1: name 一致性
    name_issues = check_name_consistency(contracts)
    if name_issues:
        print("--- name 字段一致性 ---")
        for issue in name_issues:
            print(issue)
        all_issues.extend(name_issues)
    else:
        print("--- name 字段一致性: PASS ---")

    # 检查 2: 输出文件名冲突
    collision_issues, collision_warnings = check_output_collisions(contracts, allowlist)
    if collision_issues or collision_warnings:
        print("\n--- 输出文件名冲突 ---")
        for w in collision_warnings:
            print(w)
        for issue in collision_issues:
            print(issue)
        all_issues.extend(collision_issues)
    else:
        print("--- 输出文件名冲突: PASS ---")

    # 检查 3: from_upstream 引用有效性
    upstream_issues = check_upstream_refs(contracts)
    if upstream_issues:
        print("\n--- from_upstream 引用 ---")
        for issue in upstream_issues:
            print(issue)
        all_issues.extend(upstream_issues)
    else:
        print("--- from_upstream 引用: PASS ---")

    # 汇总
    print(f"\n{'=' * 40}")
    if all_issues:
        print(f"发现 {len(all_issues)} 个问题")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
