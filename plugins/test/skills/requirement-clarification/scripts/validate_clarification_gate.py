#!/usr/bin/env python3
"""Validate requirement-clarification's pre-consolidate interaction gate."""

from __future__ import annotations

import json
import sys
import re
import argparse
from pathlib import Path


def fail(message: str) -> None:
    print(f"clarification gate failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def expect_bool(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        fail(f"{key} must be boolean")
    return value


def expect_list(data: dict, key: str) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        fail(f"{key} must be list")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate requirement-clarification's pre-consolidate interaction gate."
    )
    parser.add_argument("gate_json", help="Path to clarification_gate.json")
    parser.add_argument("--log", required=True, help="Path to clarification_log.md")
    args = parser.parse_args()

    path = Path(args.gate_json)
    if not path.exists():
        fail(f"file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")

    asked = expect_bool(data, "asked_user_questions")
    skipped = expect_bool(data, "user_confirmed_to_skip")
    can_consolidate = expect_bool(data, "can_consolidate")
    p0 = expect_list(data, "p0_open_questions")
    expect_list(data, "p1_open_questions")

    rounds = data.get("question_rounds")
    if not isinstance(rounds, int) or rounds < 0:
        fail("question_rounds must be a non-negative integer")

    skip_reason = data.get("skip_reason")
    if not asked:
        if not skipped:
            fail("must ask the user at least once or record explicit skip confirmation")
        if not isinstance(skip_reason, str) or not skip_reason.strip():
            fail("skip_reason is required when questions were not asked")

    if asked and rounds < 1:
        fail("question_rounds must be >= 1 when asked_user_questions is true")

    if p0 and not skipped:
        fail("p0_open_questions remain; ask the user or record explicit skip confirmation")

    if not can_consolidate:
        fail("can_consolidate must be true")

    log_path = Path(args.log)
    if not log_path.exists():
        fail(f"clarification log not found: {log_path}")
    log_text = log_path.read_text(encoding="utf-8")

    if asked:
        match = re.search(r"问答轮次[：:]\s*(\d+)\s*轮", log_text)
        if not match:
            fail("clarification_log.md must record question rounds")
        logged_rounds = int(match.group(1))
        if logged_rounds < rounds:
            fail("clarification_log.md question rounds are less than gate question_rounds")
        if not re.search(r"(^|\n)\s*-\s*Q:", log_text):
            fail("clarification_log.md must contain at least one recorded question")
        if not re.search(r"(^|\n)\s*-\s*A:.*\[source:\s*(human|assumption)\]", log_text):
            fail("clarification_log.md must contain at least one human-confirmed answer")
    elif skipped and str(skip_reason).strip() not in log_text:
        fail("clarification_log.md must record the skip_reason")

    print("clarification gate passed")


if __name__ == "__main__":
    main()
