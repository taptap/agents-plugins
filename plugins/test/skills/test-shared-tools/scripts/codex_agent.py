#!/usr/bin/env python3
"""
Codex Agent — 通过 OpenAI API 执行代码分析任务

供 AI Agent 在交叉验证或独立分析阶段使用。
实现 OpenAI Chat Completions + Tool Use 的 agent 循环，
让 Codex（OpenAI 模型）自主决定分析路径。

用法:
    python3 codex_agent.py --prompt "分析任务描述"
    python3 codex_agent.py --prompt "Analyze this diff..." --work-dir /path --model o3-mini
    python3 codex_agent.py --prompt "..." --timeout 300 --max-turns 20

环境变量:
    OPENAI_API_KEY    - OpenAI API Key（必需）
    OPENAI_BASE_URL   - 自定义 API 端点（可选）
    CODEX_MODEL       - 默认模型名（可选，默认 o3-mini）

输出:
    stdout: JSON 格式结果 {"findings": [...], "summary": "...", "engine": "codex", "model": "..."}
    stderr: 日志/进度信息
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ==================== .env 自动加载 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
except ImportError:
    pass

# ==================== 配置 ====================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
CODEX_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.4-mini")

# Bash 命令白名单（正则匹配命令开头）
_BASH_ALLOW_PATTERNS = [
    r'^glab\b',
    r'^gh\b',
    r'^python3?\s+\S*_helper\.py\b',
    r'^grep\b',
    r'^find\b',
    r'^wc\b',
    r'^head\b',
    r'^tail\b',
    r'^cat\b',
    r'^git\s+(diff|show|log|blame|rev-parse|ls-files)\b',
    r'^ls\b',
    r'^pwd\b',
    r'^echo\b',
    r'^sort\b',
    r'^uniq\b',
    r'^cut\b',
    r'^awk\b',
    r'^sed\s',
    r'^diff\b',
    r'^file\b',
    r'^stat\b',
]
_BASH_ALLOW_RE = re.compile('|'.join(_BASH_ALLOW_PATTERNS))

# Bash 命令黑名单（危险操作，即使通过白名单也拒绝）
_BASH_DENY_PATTERNS = [
    r'\brm\s+-r',
    r'\bcurl\b',
    r'\bwget\b',
    r'\bchmod\b',
    r'\bchown\b',
    r'\bkill\b',
    r'\bmkdir\b',
    r'\bsudo\b',
    r'\beval\b',
    r'>\s*/',           # 重定向到绝对路径
    r'\bpip\s+install',
    r'\bnpm\s+install',
]
_BASH_DENY_RE = re.compile('|'.join(_BASH_DENY_PATTERNS))

# 工具输出截断阈值（字符数）
_TOOL_OUTPUT_MAX_CHARS = 50_000


# ==================== 日志 ====================

def _log(msg: str) -> None:
    """输出日志到 stderr"""
    print(f"[codex_agent] {msg}", file=sys.stderr, flush=True)


# ==================== 工具定义 ====================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Execute a shell command. Only analysis-related commands are allowed: "
                "glab, gh, grep, find, git diff/show/log/blame, cat, head, tail, wc, "
                "python3 *_helper.py, ls, sort, uniq, cut, awk, sed, diff, file, stat. "
                "Destructive commands (rm, curl, wget, chmod, sudo, etc.) are blocked."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file within the working directory. "
                "Path must be relative to the working directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path to read",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Start line (0-based). Optional.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max lines to read. Optional, default 500.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": (
                "Search for a pattern in files within the working directory. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "Subdirectory or file to search in. Default: current dir.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g. '*.py'). Optional.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


# ==================== 工具执行 ====================

def _execute_bash(command: str, work_dir: str, timeout: int = 30) -> str:
    """执行 Bash 命令（白名单过滤）"""
    cmd_stripped = command.strip()

    # 管道命令：检查第一段
    first_cmd = cmd_stripped.split('|')[0].strip()

    if _BASH_DENY_RE.search(cmd_stripped):
        return f"ERROR: Command blocked by security policy: {cmd_stripped[:100]}"

    if not _BASH_ALLOW_RE.match(first_cmd):
        return (
            f"ERROR: Command not in allowlist. "
            f"Allowed: glab, gh, grep, find, git diff/show/log/blame, cat, head, tail, "
            f"wc, ls, sort, uniq, cut, awk, sed, diff, file, stat, python3 *_helper.py. "
            f"Got: {first_cmd[:80]}"
        )

    try:
        result = subprocess.run(
            cmd_stripped,
            shell=True,
            capture_output=True,
            text=True,
            cwd=work_dir,
            timeout=timeout,
            env={**os.environ, 'LC_ALL': 'C.UTF-8'},
        )
        output = result.stdout
        if result.returncode != 0 and result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if len(output) > _TOOL_OUTPUT_MAX_CHARS:
            output = output[:_TOOL_OUTPUT_MAX_CHARS] + f"\n... [truncated, {len(output)} chars total]"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


def _execute_read_file(path: str, work_dir: str,
                       offset: int = 0, limit: int = 500) -> str:
    """读取文件内容（路径限制在 work_dir 内）"""
    try:
        resolved = Path(work_dir, path).resolve()
        work_resolved = Path(work_dir).resolve()
        # 用 Path.is_relative_to (3.9+) 而非 startswith，避免 sibling-prefix 漏洞：
        # work_dir=/tmp/foo 时，/tmp/foobar/x 用 startswith 会通过校验
        if not (resolved == work_resolved or resolved.is_relative_to(work_resolved)):
            return f"ERROR: Path traversal blocked: {path}"

        if not resolved.is_file():
            return f"ERROR: File not found: {path}"

        lines = resolved.read_text(encoding='utf-8', errors='replace').splitlines()
        total = len(lines)
        selected = lines[offset:offset + limit]
        content = '\n'.join(f"{i + offset + 1}\t{line}" for i, line in enumerate(selected))
        if total > offset + limit:
            content += f"\n... [{total - offset - limit} more lines]"
        if len(content) > _TOOL_OUTPUT_MAX_CHARS:
            content = content[:_TOOL_OUTPUT_MAX_CHARS] + "\n... [truncated]"
        return content
    except Exception as e:
        return f"ERROR: {e}"


def _execute_grep(pattern: str, work_dir: str,
                  path: str = '.', include: str = '') -> str:
    """在工作目录内搜索文件内容"""
    cmd = ['grep', '-rn', '--color=never', '-E', pattern]
    if include:
        cmd.extend(['--include', include])
    cmd.append(path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=work_dir,
            timeout=30,
        )
        output = result.stdout
        if len(output) > _TOOL_OUTPUT_MAX_CHARS:
            output = output[:_TOOL_OUTPUT_MAX_CHARS] + "\n... [truncated]"
        return output or "(no matches)"
    except subprocess.TimeoutExpired:
        return "ERROR: grep timed out"
    except Exception as e:
        return f"ERROR: {e}"


def _execute_tool(name: str, arguments: dict, work_dir: str) -> str:
    """分派工具调用"""
    if name == "bash":
        return _execute_bash(arguments.get("command", ""), work_dir)
    elif name == "read_file":
        return _execute_read_file(
            arguments.get("path", ""),
            work_dir,
            offset=arguments.get("offset", 0),
            limit=arguments.get("limit", 500),
        )
    elif name == "grep_search":
        return _execute_grep(
            arguments.get("pattern", ""),
            work_dir,
            path=arguments.get("path", "."),
            include=arguments.get("include", ""),
        )
    else:
        return f"ERROR: Unknown tool: {name}"


# ==================== Agent Loop ====================

def _build_system_prompt() -> str:
    """构造 Codex agent 的 system prompt"""
    return (
        "You are a code analysis expert. Analyze code changes, trace call chains, "
        "identify risks, and detect logic defects.\n\n"
        "You have access to tools: bash (shell commands), read_file, grep_search.\n\n"
        "IMPORTANT: When you have completed your analysis, output your final answer as "
        "a JSON object with this structure:\n"
        "```json\n"
        '{"findings": [{"id": "CX-01", "description": "...", "severity": "HIGH|MEDIUM|LOW", '
        '"file": "path", "line": 42, "confidence": 85, "evidence": "...", '
        '"category": "risk|callchain|defect"}], '
        '"summary": "One paragraph summary of key findings"}\n'
        "```\n\n"
        "Rules:\n"
        "- Be thorough: trace call chains, check error handling, verify boundary conditions\n"
        "- Only report findings with confidence >= 50\n"
        "- Confidence guide: 90-100 = direct evidence, 70-89 = reasonable inference, "
        "50-69 = pattern-based hypothesis\n"
        "- Do NOT modify any files. Analysis only.\n"
        "- Use English for findings. Be concise but specific."
    )


def run_agent(prompt: str, work_dir: str, model: str,
              max_turns: int, timeout: int) -> dict:
    """执行 Codex agent 循环"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai package not installed", "findings": [],
                "engine": "codex", "model": model}

    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set", "findings": [],
                "engine": "codex", "model": model}

    client_kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL

    client = OpenAI(**client_kwargs)

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": prompt},
    ]

    start_time = time.time()
    turn = 0

    while turn < max_turns:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            _log(f"Timeout after {elapsed:.0f}s ({turn} turns)")
            break

        turn += 1
        _log(f"Turn {turn}/{max_turns}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                # max(5, ...) 兜底：elapsed 接近 timeout 时避免传 0/负值给 SDK
                timeout=max(5, min(120, timeout - elapsed + 5)),
            )
        except Exception as e:
            _log(f"API error: {e}")
            return {"error": str(e), "findings": [],
                    "engine": "codex", "model": model}

        choice = response.choices[0]

        # 模型完成分析，返回最终结果
        if choice.finish_reason == "stop":
            content = choice.message.content or ""
            _log(f"Completed in {turn} turns, {time.time() - start_time:.0f}s")
            return _parse_final_output(content, model)

        # 模型请求工具调用
        if choice.message.tool_calls:
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                _log(f"  Tool: {fn_name}({_summarize_args(fn_args)})")
                result = _execute_tool(fn_name, fn_args, work_dir)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
        else:
            # 无工具调用也非 stop — 异常情况
            content = choice.message.content or ""
            _log(f"Unexpected finish_reason: {choice.finish_reason}")
            return _parse_final_output(content, model)

    # max_turns 耗尽
    _log(f"Max turns ({max_turns}) exhausted")
    # 尝试从最后一条 assistant 消息中提取结果
    for msg in reversed(messages):
        if hasattr(msg, 'content') and msg.content:
            return _parse_final_output(msg.content, model)
        if isinstance(msg, dict) and msg.get('role') == 'assistant' and msg.get('content'):
            return _parse_final_output(msg['content'], model)

    return {"error": "Max turns exhausted without output", "findings": [],
            "engine": "codex", "model": model}


def _parse_final_output(content: str, model: str) -> dict:
    """从模型输出中解析 JSON 结果"""
    # 尝试从 code fence 中提取 JSON
    json_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', content)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            parsed.setdefault("engine", "codex")
            parsed.setdefault("model", model)
            return parsed
        except json.JSONDecodeError:
            pass

    # 尝试直接解析整段内容
    try:
        parsed = json.loads(content)
        parsed.setdefault("engine", "codex")
        parsed.setdefault("model", model)
        return parsed
    except json.JSONDecodeError:
        pass

    # 无法解析为 JSON，作为 summary 返回
    return {
        "findings": [],
        "summary": content[:2000],
        "engine": "codex",
        "model": model,
        "parse_warning": "Could not parse structured JSON from model output",
    }


def _summarize_args(args: dict) -> str:
    """工具参数摘要（用于日志）"""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Codex Agent: code analysis via OpenAI API",
    )
    parser.add_argument(
        "--prompt", required=True,
        help="Analysis task prompt",
    )
    parser.add_argument(
        "--work-dir", default=".",
        help="Working directory for tool execution (default: current dir)",
    )
    parser.add_argument(
        "--model", default=CODEX_MODEL,
        help=f"OpenAI model name (default: {CODEX_MODEL})",
    )
    parser.add_argument(
        "--max-turns", type=int, default=15,
        help="Max agent loop iterations (default: 15)",
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="Total timeout in seconds (default: 300)",
    )
    args = parser.parse_args()

    work_dir = str(Path(args.work_dir).resolve())
    _log(f"Starting: model={args.model}, work_dir={work_dir}, "
         f"max_turns={args.max_turns}, timeout={args.timeout}s")

    result = run_agent(
        prompt=args.prompt,
        work_dir=work_dir,
        model=args.model,
        max_turns=args.max_turns,
        timeout=args.timeout,
    )

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write('\n')
    sys.stdout.flush()


if __name__ == "__main__":
    main()
