#!/usr/bin/env python3
"""Standalone MCP server for saving TapTap QA *_cases.json files.

This is a dependency-free stdio MCP adapter for the ai-case
`mcp__cases__save_test_cases` in-process tool. It keeps the same tool name and
core validation behavior, but can run from a normal repository `.mcp.json`
without Django, pydantic, or claude_agent_sdk.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

VALID_PRIORITIES = ("P0", "P1", "P2", "P3")
MAX_TITLE_LEN = 250
DEFAULT_MODULE = "未分类"

CASE_ID_PATTERN = re.compile(r"^M(\d+)-TC-(\d+)$")
TITLE_NOISE_RE = re.compile(
    r"[(\[（【]\s*(?:AC|ac|Ac|RP|rp|Rp|CP|cp|TC|tc)\s*[-—]\s*\d+\s*[)\]）】]"
)
WORKSPACE_DIR_PATTERN = re.compile(r"^requirement_[A-Za-z0-9_.-]+$")


TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "file_path": {
            "type": "string",
            "description": (
                "Target *_cases.json absolute or repository-relative path. "
                "The resolved path must stay under CASES_MCP_ROOT/current cwd "
                "and inside a requirement_<stable_id> workspace."
            ),
        },
        "cases": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": MAX_TITLE_LEN},
                    "priority": {"type": "string", "enum": list(VALID_PRIORITIES)},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "action": {"type": "string", "minLength": 1},
                                "expected": {"type": "string"},
                            },
                            "required": ["action", "expected"],
                        },
                    },
                    "case_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "module": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "test_method": {"type": "string"},
                    "confidence": {"type": "number"},
                    "review_confidence": {"type": "number"},
                    "source": {"type": "string"},
                },
                "required": ["title", "priority", "preconditions", "steps"],
            },
            "description": (
                "Test cases. Required fields: title, priority, preconditions, steps. "
                "Each step must contain paired action and expected fields."
            ),
        },
    },
    "required": ["file_path", "cases"],
}


def _content(text: str, *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def _root() -> Path:
    raw_root = os.environ.get("CASES_MCP_ROOT") or os.getcwd()
    cwd = Path(os.getcwd()).resolve()
    raw_root = raw_root.replace("${workspaceFolder}", str(cwd))
    raw_root = raw_root.replace("${workspaceFolderBasename}", cwd.name)
    return Path(raw_root).expanduser().resolve()


def _is_allowed_workspace_path(target: Path, root: Path) -> bool:
    if WORKSPACE_DIR_PATTERN.match(root.name):
        return True

    try:
        relative = target.relative_to(root)
    except ValueError:
        return False

    parts = relative.parts
    if not parts:
        return False
    if WORKSPACE_DIR_PATTERN.match(parts[0]):
        return True
    return (
        len(parts) >= 2
        and parts[0] == ".qa-workflows"
        and WORKSPACE_DIR_PATTERN.match(parts[1]) is not None
    )


def _resolve_target(file_path: str) -> Path:
    if not file_path:
        raise ValueError("file_path 不能为空")

    target = Path(file_path)
    if not target.is_absolute():
        target = _root() / target
    target = target.resolve()

    if not target.name.endswith("_cases.json"):
        raise ValueError(f"file_path 文件名必须是 *_cases.json：{file_path}")

    root = _root()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"file_path 不在合法工作目录内：{target}；允许根目录：{root}"
        ) from exc
    if not _is_allowed_workspace_path(target, root):
        raise ValueError(
            "file_path 必须位于 requirement_<stable_id>/ 工作区内："
            f"{target}；允许根目录：{root}"
        )
    return target


def _check_text(value: str, loc: str, *, allow_empty: bool = True) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{loc} 必须是字符串，收到 {type(value).__name__}")
    if not allow_empty and not value:
        raise ValueError(f"{loc} 不可为空")
    if '"' in value:
        raise ValueError(f'{loc} 不允许出现 ASCII 双引号 (")，请改用中文引号「」')


def _normalize_module(value: Any) -> str:
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return DEFAULT_MODULE


def _validate_cases(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raise ValueError(
            f"用例文件顶层必须是 JSON 数组，收到 dict（含键 {list(raw.keys())[:5]}）"
        )
    if not isinstance(raw, list):
        raise ValueError(f"用例文件顶层必须是 JSON 数组，收到 {type(raw).__name__}")
    if not raw:
        raise ValueError("用例数组为空，至少需要 1 条用例")

    allowed = {
        "title",
        "priority",
        "preconditions",
        "steps",
        "case_id",
        "module",
        "test_method",
        "confidence",
        "review_confidence",
        "source",
    }
    errors: list[str] = []
    seen: dict[tuple[str, str], int] = {}

    for idx, case in enumerate(raw):
        title = case.get("title", "<未命名>") if isinstance(case, dict) else "<非对象>"
        prefix = f"[{idx}] {title}"
        if not isinstance(case, dict):
            errors.append(f"{prefix} → <root>: 用例必须是 object")
            continue

        extra = sorted(set(case) - allowed)
        if extra:
            if "name" in extra and "title" not in case:
                errors.append(f"{prefix} → name: 字段 name 不被接受，必须使用 title")
            elif "prerequisite" in extra and "preconditions" not in case:
                errors.append(
                    f"{prefix} → prerequisite: 字段 prerequisite 不被接受，必须使用 preconditions"
                )
            elif "expected" in extra:
                errors.append(f"{prefix} → expected: expected 不能出现在用例顶层")
            elif "tags" in extra:
                errors.append(f"{prefix} → tags: tags 不能由 AI 写入用例")
            else:
                errors.append(f"{prefix} → <root>: 不支持字段 {extra}")
            continue

        for field in ("title", "priority", "preconditions", "steps"):
            if field not in case:
                errors.append(f"{prefix} → {field}: 缺少必填字段")

        case_id = case.get("case_id")
        if case_id is not None and not isinstance(case_id, str):
            errors.append(f"{prefix} → case_id: 必须是字符串；AI 生成时可省略，由系统补齐")

        module = case.get("module")
        if module is not None and not isinstance(module, str):
            errors.append(f"{prefix} → module: 必须是字符串、null 或省略；缺失/null/空字符串会归为 {DEFAULT_MODULE}")
        case["module"] = _normalize_module(module)

        for field in ("test_method", "source"):
            value = case.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"{prefix} → {field}: 必须是字符串或省略")

        for field in ("confidence", "review_confidence"):
            value = case.get(field)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                errors.append(f"{prefix} → {field}: 必须是数字或省略")

        try:
            _check_text(case.get("title", ""), "title", allow_empty=False)
            if len(case["title"]) > MAX_TITLE_LEN:
                errors.append(f"{prefix} → title: 超过 {MAX_TITLE_LEN} 字符")
            if TITLE_NOISE_RE.search(case["title"]):
                errors.append(f"{prefix} → title: 不允许包含内部追溯标记")
        except Exception as exc:
            errors.append(f"{prefix} → title: {exc}")

        if case.get("priority") not in VALID_PRIORITIES:
            errors.append(f"{prefix} → priority: 只允许 P0/P1/P2/P3")

        preconditions = case.get("preconditions")
        if not isinstance(preconditions, list):
            errors.append(
                f"{prefix} → preconditions: 必须是字符串数组，收到 {type(preconditions).__name__}"
            )
        else:
            for i, item in enumerate(preconditions):
                try:
                    _check_text(item, f"preconditions[{i}]")
                except Exception as exc:
                    errors.append(f"{prefix} → preconditions[{i}]: {exc}")

        steps = case.get("steps")
        if isinstance(steps, list) and steps and isinstance(steps[0], (str, bytes)):
            errors.append(f"{prefix} → steps: 必须是 {{action, expected}} 对象数组")
        elif not isinstance(steps, list) or not steps:
            errors.append(f"{prefix} → steps: 至少需要 1 个步骤")
        else:
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(f"{prefix} → steps[{i}]: step 必须是 object")
                    continue
                step_extra = sorted(set(step) - {"action", "expected"})
                if step_extra:
                    errors.append(f"{prefix} → steps[{i}]: 不支持字段 {step_extra}")
                for field in ("action", "expected"):
                    if field not in step:
                        errors.append(f"{prefix} → steps[{i}].{field}: 缺少必填字段")
                        continue
                    try:
                        _check_text(step[field], f"steps[{i}].{field}", allow_empty=(field == "expected"))
                    except Exception as exc:
                        errors.append(f"{prefix} → steps[{i}].{field}: {exc}")

        key = (_normalize_module(case.get("module")), str(case.get("title") or "").strip())
        if key in seen:
            errors.append(
                f"{prefix} → title: 同 module「{key[0] or '<未指定>'}」内 title 重复"
                f"（首次出现于 index {seen[key]}）"
            )
        else:
            seen[key] = idx

    if errors:
        head = "\n".join(f"  {line}" for line in errors[:20])
        more = f"\n  ...（共 {len(errors)} 个错误，仅展示前 20）" if len(errors) > 20 else ""
        raise ValueError(f"用例校验失败（{len(errors)} 处）：\n{head}{more}")

    return raw


def _scan_existing_cases(work_dir: Path, exclude_file: Path) -> tuple[dict[str, int], dict[str, int], int]:
    module_to_index: dict[str, int] = {}
    module_max_seq: dict[str, int] = {}
    if not work_dir.is_dir():
        return module_to_index, module_max_seq, 1

    case_files: list[list[Any]] = []
    for fpath in sorted(work_dir.glob("*_cases.json")):
        try:
            if fpath.resolve() == exclude_file.resolve():
                continue
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            case_files.append(data)

    for cases in case_files:
        for case in cases:
            if not isinstance(case, dict):
                continue
            module = _normalize_module(case.get("module"))
            match = CASE_ID_PATTERN.match(case.get("case_id") or "")
            if match:
                idx = int(match.group(1))
                seq = int(match.group(2))
                module_to_index.setdefault(module, idx)
                module_max_seq[module] = max(module_max_seq.get(module, 0), seq)

    next_index = max(module_to_index.values(), default=0) + 1
    for cases in case_files:
        for case in cases:
            if not isinstance(case, dict):
                continue
            module = _normalize_module(case.get("module"))
            if module not in module_to_index:
                module_to_index[module] = next_index
                next_index += 1

    return module_to_index, module_max_seq, next_index


def _assign_case_ids(cases: list[Any], target: Path) -> int:
    module_to_index, module_max_seq, next_index = _scan_existing_cases(target.parent, target)

    for case in cases:
        if not isinstance(case, dict):
            continue
        module = _normalize_module(case.get("module"))
        match = CASE_ID_PATTERN.match(case.get("case_id") or "")
        if match:
            idx = int(match.group(1))
            seq = int(match.group(2))
            if module not in module_to_index:
                module_to_index[module] = idx
                next_index = max(next_index, idx + 1)
            module_max_seq[module] = max(module_max_seq.get(module, 0), seq)

    for case in cases:
        if not isinstance(case, dict):
            continue
        module = _normalize_module(case.get("module"))
        if module not in module_to_index:
            module_to_index[module] = next_index
            next_index += 1

    assigned = 0
    for case in cases:
        if not isinstance(case, dict) or case.get("case_id"):
            continue
        module = _normalize_module(case.get("module"))
        idx = module_to_index[module]
        seq = module_max_seq.get(module, 0) + 1
        module_max_seq[module] = seq
        case["case_id"] = f"M{idx}-TC-{seq:02d}"
        assigned += 1
    return assigned


def save_test_cases(args: dict[str, Any]) -> dict[str, Any]:
    try:
        target = _resolve_target(str(args.get("file_path", "")))
        cases_raw = args.get("cases", [])
        assigned = _assign_case_ids(cases_raw, target) if isinstance(cases_raw, list) else 0
        cases = _validate_cases(cases_raw)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        msg = f"已保存 {len(cases)} 条用例到 {target}"
        if assigned:
            msg += f"（自动分配 {assigned} 条 case_id）"
        return _content(msg)
    except Exception as exc:
        return _content(str(exc), is_error=True)


def _read_message() -> dict[str, Any] | None:
    first = sys.stdin.buffer.readline()
    if not first:
        return None
    if first.startswith(b"Content-Length:"):
        length = int(first.split(b":", 1)[1].strip())
        while True:
            line = sys.stdin.buffer.readline()
            if line in (b"\r\n", b"\n", b""):
                break
        body = sys.stdin.buffer.read(length)
        return json.loads(body.decode("utf-8"))
    return json.loads(first.decode("utf-8"))


def _write_message(message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    sys.stdout.buffer.flush()


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in request:
        return None
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cases", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [{
                    "name": "save_test_cases",
                    "description": (
                        "保存测试用例到 *_cases.json 文件。schema 会强校验字段，"
                        "并为缺失 case_id 的用例自动分配 M{N}-TC-{NN}。"
                    ),
                    "inputSchema": TOOL_SCHEMA,
                }],
            },
        }
    if method == "tools/call":
        params = request.get("params") or {}
        if params.get("name") != "save_test_cases":
            result = _content(f"未知工具：{params.get('name')}", is_error=True)
        else:
            result = save_test_cases(params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    while True:
        try:
            request = _read_message()
            if request is None:
                return 0
            response = _handle(request)
            if response is not None:
                _write_message(response)
        except Exception as exc:
            _write_message({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            })


if __name__ == "__main__":
    raise SystemExit(main())
