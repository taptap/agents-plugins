#!/bin/bash
# ensure-codex-plugins.sh - taptap-plugins 远端 marketplace 自愈 + 插件 enable/install
#
# SessionStart hook：同步执行，保证首轮对话前 plugin 已可见可用。
#
# 远端源策略（Codex 0.121.0+）：
#   1. 以 ~/.codex/.tmp/marketplaces/taptap-plugins/ 下的远端安装元数据和 clone 为准。
#   2. 如检测到旧本地源 / 错误源 / 损坏 clone，清理 runtime state 后重新注册
#      `codex plugin marketplace add taptap/agents-plugins`（兼容旧版
#      `codex marketplace add`）。
#   3. 把项目根 .codex/config.toml 中 enabled = true 的 *@taptap-plugins 镜像到
#      用户级 ~/.codex/config.toml。
#   4. 从远端 marketplace clone 中为 enabled 插件补齐 ~/.codex/plugins/cache/...，
#      避免 Git source marketplace 仍需 TUI 手动 install。

set -euo pipefail

CODEX_CONFIG_FILE="$HOME/.codex/config.toml"
MARKETPLACE_NAME="taptap-plugins"
MARKETPLACE_GITHUB="taptap/agents-plugins"
EXPECTED_REMOTE_SOURCE="github:taptap/agents-plugins"
LOG_DIR="$HOME/.codex/log/ensure-codex-plugins"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"
LOCK_DIR="$HOME/.codex/locks/ensure-codex-plugins.lock"
LOCK_OWNER_PID="$$"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROJECT_CONFIG_FILE="$PROJECT_ROOT/.codex/config.toml"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

has_command() { command -v "$1" >/dev/null 2>&1; }

if ! has_command python3; then
  echo "⚠️  未检测到 python3，跳过 Codex 插件同步"
  exit 0
fi

lock_status=$(
  LOCK_DIR="$LOCK_DIR" LOCK_OWNER_PID="$LOCK_OWNER_PID" python3 - <<'PY'
import json
import os
import shutil
import time
from pathlib import Path

lock_dir = Path(os.environ["LOCK_DIR"])
owner_pid = int(os.environ["LOCK_OWNER_PID"])
owner_file = lock_dir / "owner.json"
fresh_lock_grace_seconds = 5.0


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_owner() -> None:
    owner_file.write_text(
        json.dumps({"pid": owner_pid, "created_at": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )


def try_acquire() -> bool:
    try:
        lock_dir.mkdir(parents=True)
    except FileExistsError:
        return False
    write_owner()
    return True


if try_acquire():
    print("acquired")
    raise SystemExit(0)

stale = False
lock_age = time.time() - lock_dir.stat().st_mtime if lock_dir.exists() else 0.0
if not owner_file.is_file():
    stale = lock_age > fresh_lock_grace_seconds
else:
    try:
        payload = json.loads(owner_file.read_text(encoding="utf-8"))
    except Exception:
        payload = None

    if not isinstance(payload, dict):
        stale = lock_age > fresh_lock_grace_seconds
    else:
        existing_pid = payload.get("pid")
        created_at = payload.get("created_at")
        if not isinstance(existing_pid, int):
            stale = lock_age > fresh_lock_grace_seconds
        elif not pid_alive(existing_pid):
            stale = True
        elif not isinstance(created_at, (int, float)):
            stale = lock_age > fresh_lock_grace_seconds
        elif (time.time() - float(created_at)) > 300:
            stale = True

if stale:
    shutil.rmtree(lock_dir, ignore_errors=True)
    if try_acquire():
        print("acquired")
    else:
        print("busy")
else:
    print("busy")
PY
)

if [ "$lock_status" != "acquired" ]; then
  echo "ℹ️  另一个 ensure-codex-plugins.sh 正在执行，跳过当前调用"
  exit 0
fi

release_lock() {
  LOCK_DIR="$LOCK_DIR" LOCK_OWNER_PID="$LOCK_OWNER_PID" python3 - <<'PY'
import json
import os
import shutil
from pathlib import Path

lock_dir = Path(os.environ["LOCK_DIR"])
owner_pid = int(os.environ["LOCK_OWNER_PID"])
owner_file = lock_dir / "owner.json"
if not lock_dir.exists():
    raise SystemExit(0)

try:
    payload = json.loads(owner_file.read_text(encoding="utf-8")) if owner_file.is_file() else {}
except Exception:
    payload = {}

if payload.get("pid") == owner_pid:
    shutil.rmtree(lock_dir, ignore_errors=True)
PY
}

trap release_lock EXIT

HAS_CODEX=0
if has_command codex; then
  HAS_CODEX=1
fi

if ! PROJECT_CONFIG_FILE="$PROJECT_CONFIG_FILE" \
  CODEX_CONFIG_FILE="$CODEX_CONFIG_FILE" \
  MARKETPLACE_NAME="$MARKETPLACE_NAME" \
  MARKETPLACE_GITHUB="$MARKETPLACE_GITHUB" \
  EXPECTED_REMOTE_SOURCE="$EXPECTED_REMOTE_SOURCE" \
  HAS_CODEX="$HAS_CODEX" \
  python3 - <<'PY'
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

project_config = Path(os.environ["PROJECT_CONFIG_FILE"])
user_config = Path(os.environ["CODEX_CONFIG_FILE"])
marketplace = os.environ["MARKETPLACE_NAME"]
marketplace_github = os.environ["MARKETPLACE_GITHUB"]
expected_remote = os.environ["EXPECTED_REMOTE_SOURCE"]
has_codex = os.environ["HAS_CODEX"] == "1"
clone_path = Path.home() / ".codex/.tmp/marketplaces" / marketplace
cache_root = Path.home() / ".codex/plugins/cache" / marketplace
install_file = clone_path / ".codex-marketplace-install.json"
marketplace_json = clone_path / ".agents/plugins/marketplace.json"
suffix = f"@{marketplace}"


def normalize_source(source, source_type=""):
    if not isinstance(source, str):
        return ""
    s = source.strip()
    if not s:
        return ""
    if source_type == "local" or s.startswith(("/", "./", "../", "~/")):
        return f"local:{s}"

    github_http = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s)
    if github_http:
        return f"github:{github_http.group(1)}/{github_http.group(2)}"

    github_ssh = re.match(r"^(?:git@github\.com:|ssh://git@github\.com/)([^/]+)/([^/]+?)(?:\.git)?/?$", s)
    if github_ssh:
        return f"github:{github_ssh.group(1)}/{github_ssh.group(2)}"

    shorthand = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", s)
    if shorthand:
        return f"github:{shorthand.group(1)}/{shorthand.group(2)}"

    return f"raw:{s}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def parse_marketplace_config_block(path: Path):
    text = read_text(path)
    block_re = re.compile(rf'(?ms)^\[marketplaces\.{re.escape(marketplace)}\]\s*\n.*?(?=^\[|\Z)')
    match = block_re.search(text)
    if not match:
        return None
    block = match.group(0)
    source_type_match = re.search(r'(?mi)^source_type\s*=\s*"([^"]+)"\s*$', block)
    source_match = re.search(r'(?mi)^source\s*=\s*"([^"]+)"\s*$', block)
    return {
        "block": block,
        "source_type": source_type_match.group(1) if source_type_match else "",
        "source": source_match.group(1) if source_match else "",
    }


def remove_marketplace_config_block(path: Path):
    text = read_text(path)
    block_re = re.compile(rf'(?ms)^\[marketplaces\.{re.escape(marketplace)}\]\s*\n.*?(?=^\[|\Z)')
    new_text, count = block_re.subn("", text)
    if count:
        new_text = re.sub(r"\n{3,}", "\n\n", new_text).lstrip("\n")
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
    return count > 0


def load_enabled(path: Path):
    if not path.is_file():
        return []
    enabled = []
    current_id = None
    current_enabled = False
    section_re = re.compile(rf'^\[plugins\."([^"]+{re.escape(suffix)})"\]\s*$')

    def flush():
        if current_id and current_enabled and current_id not in enabled:
            enabled.append(current_id)

    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        match = section_re.match(s)
        if match:
            flush()
            current_id = match.group(1)
            current_enabled = False
            continue
        if current_id is not None and s.startswith("["):
            flush()
            current_id = None
            current_enabled = False
            continue
        if current_id is None:
            continue
        enabled_match = re.match(r"^enabled\s*=\s*(true|false)\s*$", s, re.IGNORECASE)
        if enabled_match:
            current_enabled = enabled_match.group(1).lower() == "true"

    flush()
    return enabled


def ensure_enabled(path: Path, plugin_ids):
    if not plugin_ids:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    text = read_text(path)
    updated = []
    for pid in plugin_ids:
        block_re = re.compile(rf'(?ms)^\[plugins\."{re.escape(pid)}"\]\s*\n.*?(?=^\[|\Z)')
        match = block_re.search(text)
        if match:
            block = match.group(0)
            if re.search(r"(?mi)^enabled\s*=\s*true\s*$", block):
                continue
            if re.search(r"(?mi)^enabled\s*=\s*false\s*$", block):
                continue
            new_block = block.rstrip("\n") + "\nenabled = true\n"
            text = text[: match.start()] + new_block + text[match.end():]
            updated.append(pid)
            continue

        if text and not text.endswith("\n\n"):
            text = text.rstrip("\n") + "\n\n"
        text += f'[plugins."{pid}"]\nenabled = true\n'
        updated.append(pid)

    if updated:
        if text and not text.endswith("\n"):
            text += "\n"
        path.write_text(text, encoding="utf-8")
    return updated


def read_git_origin_url(path: Path):
    git_path = path / ".git"
    config_path = git_path / "config"

    if git_path.is_file():
        try:
            gitdir_line = git_path.read_text(encoding="utf-8").strip()
        except Exception:
            gitdir_line = ""
        if gitdir_line.startswith("gitdir:"):
            resolved = (path / gitdir_line.split(":", 1)[1].strip()).resolve()
            config_path = resolved / "config"

    if not config_path.is_file():
        return ""

    parser = configparser.RawConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except Exception:
        return ""

    section = 'remote "origin"'
    if parser.has_option(section, "url"):
        return parser.get(section, "url")
    return ""


def detect_marketplace_state():
    install_payload = {}
    if install_file.is_file():
        try:
            install_payload = json.loads(install_file.read_text(encoding="utf-8"))
        except Exception as exc:
            install_payload = {"_parse_error": str(exc)}

    source_type = install_payload.get("source_type", "") if isinstance(install_payload, dict) else ""
    source = install_payload.get("source", "") if isinstance(install_payload, dict) else ""
    normalized_install = normalize_source(source, source_type)
    origin_url = read_git_origin_url(clone_path)
    normalized_origin = normalize_source(origin_url, "git")
    has_marketplace_json = marketplace_json.is_file()

    state = "missing"
    reason = "marketplace clone 不存在"

    if has_marketplace_json and (normalized_install == expected_remote or normalized_origin == expected_remote):
        state = "healthy_remote"
        reason = "远端 marketplace clone 正常"
    elif normalized_install and normalized_install != expected_remote:
        state = "local_or_mismatched"
        reason = f"安装元数据 source={normalized_install}"
    elif normalized_origin and normalized_origin != expected_remote:
        state = "local_or_mismatched"
        reason = f"git origin={normalized_origin}"
    elif has_marketplace_json and not (normalized_install or normalized_origin):
        state = "unknown_clone"
        reason = "clone 存在但缺少远端来源元数据"
    elif (normalized_install == expected_remote or normalized_origin == expected_remote) and not has_marketplace_json:
        state = "broken_remote"
        reason = "远端 marketplace 元数据存在但 clone 不完整"
    elif install_file.is_file() and isinstance(install_payload, dict) and install_payload.get("_parse_error"):
        state = "broken_remote"
        reason = f"安装元数据解析失败: {install_payload['_parse_error']}"

    return {
        "state": state,
        "reason": reason,
        "source_type": source_type,
        "source": source,
        "normalized_install": normalized_install,
        "origin_url": origin_url,
        "normalized_origin": normalized_origin,
        "has_marketplace_json": has_marketplace_json,
        "has_install_file": install_file.is_file(),
    }


def reset_runtime_state():
    shutil.rmtree(clone_path, ignore_errors=True)
    shutil.rmtree(cache_root, ignore_errors=True)


def print_process_output(prefix, completed):
    output = "\n".join(
        part.strip()
        for part in [completed.stdout or "", completed.stderr or ""]
        if isinstance(part, str) and part.strip()
    )
    if not output:
        return
    for line in output.splitlines():
        print(f"{prefix}{line}")


def detect_personal_marketplace_conflict():
    personal_marketplace = Path.home() / ".agents/plugins/marketplace.json"
    if not personal_marketplace.is_file():
        return ""
    try:
        payload = json.loads(personal_marketplace.read_text(encoding="utf-8"))
    except Exception:
        return str(personal_marketplace)
    if isinstance(payload, dict) and payload.get("name") == marketplace:
        return str(personal_marketplace)
    return ""


def resolve_marketplace_cli(action):
    candidates = [
        ["codex", "plugin", "marketplace", action],
        ["codex", "marketplace", action],
    ]
    for candidate in candidates:
        probe = subprocess.run(
            candidate + ["--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return candidate
    return []


def ensure_remote_marketplace():
    state = detect_marketplace_state()
    cfg_state = parse_marketplace_config_block(user_config)
    if state["state"] == "healthy_remote":
        print(f"ℹ️  marketplace {marketplace} 已是远端 GitHub 源，跳过 marketplace add")
        return state

    if cfg_state:
        normalized_cfg = normalize_source(cfg_state["source"], cfg_state["source_type"])
        if normalized_cfg and normalized_cfg != expected_remote:
            if remove_marketplace_config_block(user_config):
                print(f"ℹ️  已移除用户配置中的旧 marketplace 段: {normalized_cfg}")

    if state["state"] in {"local_or_mismatched", "broken_remote", "unknown_clone"}:
        print(f"⚠️  marketplace {marketplace} 状态异常，准备切换到远端 GitHub 源: {state['reason']}")
        reset_runtime_state()
    else:
        print(f"ℹ️  marketplace {marketplace} 未就绪，准备注册远端 GitHub 源")

    if not has_codex:
        print("⚠️  codex CLI 不在 PATH，无法注册远端 marketplace；继续执行 Step 2/3")
        return detect_marketplace_state()

    add_cli = resolve_marketplace_cli("add")
    remove_cli = resolve_marketplace_cli("remove")
    if not add_cli:
        print(
            "⚠️  当前 codex CLI 不支持 marketplace add；"
            "已尝试 `codex plugin marketplace add` 和 `codex marketplace add`，继续执行 Step 2/3"
        )
        return detect_marketplace_state()

    add_label = " ".join(add_cli)
    completed = subprocess.run(
        add_cli + [marketplace_github],
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode == 0:
        print(f"✅ 已注册远端 marketplace {marketplace}: {marketplace_github}")
        print_process_output("    ", completed)
    else:
        print(f"⚠️  {add_label} 失败: {marketplace_github}")
        print_process_output("    ", completed)
        output = "\n".join(
            part.strip()
            for part in [completed.stdout or "", completed.stderr or ""]
            if isinstance(part, str) and part.strip()
        )
        if "already added from a different source" in output and remove_cli:
            remove_label = " ".join(remove_cli)
            print(f"⚠️  检测到 marketplace source 冲突，尝试先移除再重建: {remove_label} {marketplace}")
            remove_completed = subprocess.run(
                remove_cli + [marketplace],
                text=True,
                capture_output=True,
                check=False,
            )
            print_process_output("    ", remove_completed)
            if remove_completed.returncode == 0:
                completed = subprocess.run(
                    add_cli + [marketplace_github],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if completed.returncode == 0:
                    print(f"✅ 移除旧源后已重新注册远端 marketplace {marketplace}: {marketplace_github}")
                else:
                    print(f"⚠️  移除旧源后再次执行 {add_label} 仍失败: {marketplace_github}")
                print_process_output("    ", completed)

    final_state = detect_marketplace_state()
    if final_state["state"] == "healthy_remote":
        print(f"✅ marketplace {marketplace} 当前为远端 GitHub 源")
        return final_state

    personal_conflict = detect_personal_marketplace_conflict()
    if personal_conflict:
        print(f"⚠️  检测到个人 marketplace 可能冲突，请手动检查: {personal_conflict}")

    print(
        "⚠️  当前未能把 marketplace 修复到远端源；"
        "已继续执行 Step 2/3。若首次发现仍失败，请清理 "
        "~/.codex/.tmp/marketplaces/taptap-plugins 和 "
        "~/.codex/plugins/cache/taptap-plugins 后重试"
    )
    return final_state


def load_marketplace_payload():
    if not marketplace_json.is_file():
        print(f"⚠️  marketplace clone 不在 {clone_path}，跳过 cache install")
        return {}
    try:
        return json.loads(marketplace_json.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️  解析 marketplace.json 失败: {exc}")
        return {}


def step_install_from_remote_clone():
    marketplace_payload = load_marketplace_payload()
    if not marketplace_payload:
        return

    default_install = []
    plugin_meta = {}
    for entry in marketplace_payload.get("plugins", []):
        name = entry.get("name")
        if not name:
            continue
        src = entry.get("source", {})
        src_path = src.get("path", "").lstrip("./") if isinstance(src, dict) else ""
        if not src_path:
            continue

        src_dir = clone_path / src_path
        manifest = src_dir / ".codex-plugin/plugin.json"
        if not manifest.is_file():
            print(f"⚠️  plugin {name} 在远端 clone 中缺 .codex-plugin/plugin.json，跳过")
            continue

        try:
            version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "0.0.0")
        except Exception:
            version = "0.0.0"

        plugin_meta[name] = {"src_dir": src_dir, "version": version}
        if entry.get("policy", {}).get("installation", "AVAILABLE") == "INSTALLED_BY_DEFAULT":
            default_install.append(name)

    config_text = read_text(user_config)
    auto_enabled = []
    for name in default_install:
        pid = f"{name}{suffix}"
        block_re = re.compile(rf'(?ms)^\[plugins\."{re.escape(pid)}"\]\s*\n.*?(?=^\[|\Z)')
        match = block_re.search(config_text)
        if match:
            block = match.group(0)
            if re.search(r"(?mi)^enabled\s*=\s*(true|false)\s*$", block):
                continue
            new_block = block.rstrip("\n") + "\nenabled = true\n"
            config_text = config_text[: match.start()] + new_block + config_text[match.end():]
            auto_enabled.append(pid)
            continue
        if config_text and not config_text.endswith("\n\n"):
            config_text = config_text.rstrip("\n") + "\n\n"
        config_text += f'[plugins."{pid}"]\nenabled = true\n'
        auto_enabled.append(pid)

    if auto_enabled:
        user_config.parent.mkdir(parents=True, exist_ok=True)
        if not config_text.endswith("\n"):
            config_text += "\n"
        user_config.write_text(config_text, encoding="utf-8")
        print(f"✅ 默认 enable INSTALLED_BY_DEFAULT 插件: {', '.join(auto_enabled)}")

    enabled_now = load_enabled(user_config)
    installed = []
    skipped = []
    for pid in enabled_now:
        name = pid.split("@", 1)[0]
        if name not in plugin_meta:
            continue
        info = plugin_meta[name]
        target = cache_root / name / info["version"]
        target_manifest = target / ".codex-plugin/plugin.json"
        if target_manifest.is_file():
            skipped.append(f"{name}@{info['version']}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(info["src_dir"], target)
        installed.append(f"{name}@{info['version']}")

    if installed:
        print(f"✅ 已 install 到 cache: {', '.join(installed)}")
    if skipped:
        print(f"ℹ️  cache 中已存在，跳过: {', '.join(skipped)}")


marketplace_state = ensure_remote_marketplace()

if project_config.is_file():
    desired = load_enabled(project_config)
    updated = ensure_enabled(user_config, desired)
    if updated:
        print("✅ 已镜像项目插件到用户配置: " + ", ".join(updated))
    elif desired:
        print("ℹ️  用户配置中已满足项目声明的插件启用状态，无需更新")

step_install_from_remote_clone()

if marketplace_state["state"] == "healthy_remote":
    print(f"✅ Codex 插件配置已就绪：marketplace={marketplace} source=remote")
else:
    print(f"⚠️  Codex 插件配置部分完成：marketplace={marketplace} source 未就绪")
PY
then
  echo "⚠️  ensure-codex-plugins.sh 执行异常，已跳过"
fi
