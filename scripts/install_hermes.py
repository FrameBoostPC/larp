#!/usr/bin/env python3
"""Install the shared Hermes policy and skills into an explicitly selected profile.

Dry-run by default. Optional --n8n-url adds an OAuth MCP connection; login is a
separate user step. This does not install Hermes or copy credentials.
Existing content is replaced only when its last installed hash agrees.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import uuid


ROOT = Path(__file__).resolve().parents[1]
OWNER = "hermes-agent-skills"
STATE_PATH = f"{OWNER}/.install-state.json"
LOCK_PATH = f"{OWNER}/.install.lock"
START = b"<!-- hermes-agent-skills:begin -->"
END = b"<!-- hermes-agent-skills:end -->"
RESOURCES = ("instructions.md", "capabilities.json", "workflow-contracts.md", "setup-contract.md", "settings.py")
RETIRED_SKILLS = frozenset({"research-brief"})
UNCHECKED = object()
N8N_TOOLS = ("search_workflows", "get_workflow_details", "execute_workflow", "get_workflow_execution")


def n8n_config(raw: bytes, endpoint: str, server_name: str) -> tuple[bytes, str]:
    """Add one MCP entry without rewriting unrelated YAML or exposing its values.

    Existing matching connections (including their auth and tool filters) are
    preserved. Unusual YAML is rejected for explicit reconciliation, never guessed.
    """
    try:
        parsed = urlsplit(endpoint)
        parsed.port  # Validate a supplied port without echoing the URL on failure.
    except ValueError as exc:
        raise InstallError("Use a valid HTTPS instance MCP URL without credentials") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") != "/mcp-server/http"
            or re.search(r"[\s\x00-\x1f]", endpoint)):
        raise InstallError("Use the HTTPS instance MCP URL ending in /mcp-server/http, without credentials or query parameters")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", server_name):
        raise InstallError("MCP server name must use lowercase letters, digits, underscores or hyphens")
    endpoint = endpoint.rstrip("/")
    try:
        import yaml
    except ImportError as exc:
        raise InstallError("Optional MCP setup requires PyYAML; install requirements-dev.txt with this Python interpreter") from exc

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise InstallError("config.yaml has duplicate or non-string mapping keys; reconcile it first")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)

    def load(text):
        try:
            return yaml.load(text, Loader=UniqueLoader), yaml.compose(text, Loader=UniqueLoader)
        except (yaml.YAMLError, RecursionError, ValueError) as exc:
            # YAML error strings can contain entire lines, including secrets.
            raise InstallError("Cannot safely merge config.yaml; check its YAML structure locally") from exc

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InstallError("config.yaml must use UTF-8") from exc
    config, root = load(text)
    if not isinstance(config, dict) or not isinstance(root, yaml.MappingNode) or root.flow_style:
        raise InstallError("config.yaml must contain one block-style settings mapping")
    servers = config.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        raise InstallError("mcp_servers must be a mapping; reconcile config.yaml first")
    matches = [(name, value) for name, value in servers.items()
               if isinstance(value, dict) and isinstance(value.get("url"), str)
               and value["url"].rstrip("/") == endpoint]
    if len(matches) > 1:
        if server_name not in dict(matches):
            raise InstallError("Several connections use this endpoint; select one with --n8n-server-name")
        matches = [(server_name, servers[server_name])]
    if matches:
        name, existing = matches[0]
        if existing.get("enabled") is False:
            raise InstallError("The matching MCP connection is disabled; explicitly enable it in Hermes before setup")
        if existing.get("command"):
            raise InstallError("The matching MCP connection mixes transports; reconcile it in Hermes")
        return raw, name
    if server_name in servers:
        raise InstallError("That MCP server name is already used; choose a different --n8n-server-name")

    entry = {"url": endpoint, "auth": "oauth", "timeout": 360,
             "tools": {"include": list(N8N_TOOLS)}}
    eol = "\r\n" if "\r\n" in text else "\n"
    mcp_node = next((v for k, v in root.value if k.value == "mcp_servers"), None)
    generated = yaml.safe_dump({server_name: entry}, sort_keys=False).rstrip("\n")
    if mcp_node is None:
        addition = "mcp_servers:" + eol + eol.join("  " + line for line in generated.splitlines()) + eol
        merged = text + ("" if text.endswith(("\n", "\r")) else eol) + addition
    elif isinstance(mcp_node, yaml.MappingNode) and mcp_node.value and not mcp_node.flow_style:
        first_key = mcp_node.value[0][0]
        start = text.rfind("\n", 0, first_key.start_mark.index) + 1
        indent = " " * first_key.start_mark.column
        addition = eol.join(indent + line for line in generated.splitlines()) + eol
        merged = text[:start] + addition + text[start:]
    elif not servers and (isinstance(mcp_node, yaml.MappingNode)
                          or isinstance(mcp_node, yaml.ScalarNode) and mcp_node.tag.endswith(":null")):
        addition = eol + eol.join("  " + line for line in generated.splitlines())
        merged = text[:mcp_node.start_mark.index] + addition + text[mcp_node.end_mark.index:]
    else:
        raise InstallError("mcp_servers uses unsupported YAML layout; merge the documented entry locally")
    expected = dict(config)
    expected["mcp_servers"] = {**servers, server_name: entry}
    after, _ = load(merged)
    if after != expected:
        raise InstallError("MCP insertion would change unrelated settings; merge the documented entry locally")
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return bom + merged.encode("utf-8"), server_name


def add_n8n_to_plan(plan: dict, endpoint: str, server_name: str) -> str:
    """Use the installer's lock, backups and concurrent-edit checks for config too.

    config.yaml is deliberately not added to installer ownership. Future installs
    without --n8n-url leave it alone, including the user's later connection edits.
    """
    path = target_path(plan["home"], "config.yaml")
    original = read_optional(path)
    if original is None:
        raise InstallError("MCP setup requires the existing active Hermes profile's config.yaml; complete Hermes setup and check --hermes-home")
    updated, selected = n8n_config(original, endpoint, server_name)
    plan["before"]["config.yaml"] = original
    if updated != original:
        plan["changes"]["config.yaml"] = updated
    return selected


class InstallError(ValueError):
    """A profile conflict that must be reconciled without overwriting user work."""


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def checked_path(path: Path) -> Path:
    """Refuse links, including Windows junctions, before resolving a target."""
    absolute = Path(os.path.abspath(path.expanduser()))
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise InstallError(f"Linked paths are not supported: {part}")
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise InstallError(f"Reparse points are not supported: {part}")
    return absolute.resolve()


def target_path(home: Path, relative: str) -> Path:
    relative_path = PurePosixPath(relative)
    if (not relative or relative_path.is_absolute() or ".." in relative_path.parts
            or "\\" in relative or ":" in relative):
        raise InstallError(f"Invalid installed path: {relative!r}")
    path = checked_path(home.joinpath(*relative_path.parts))
    if not path.is_relative_to(home):
        raise InstallError(f"Installed path leaves profile: {relative}")
    return path


def read_optional(path: Path) -> bytes | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise InstallError(f"Expected a regular file: {path}")
    return path.read_bytes()


def collect_sources(root: Path) -> dict[str, bytes]:
    files = {}
    for name in RESOURCES:
        path = checked_path(root / "components" / "hermes-orchestration" / name)
        if not path.is_file():
            raise InstallError(f"Missing orchestration source: {path}")
        files[f"{OWNER}/{name}"] = path.read_bytes()
    skills_dir = checked_path(root / "skills")
    skills = [p for p in sorted(skills_dir.iterdir())
              if not p.name.startswith((".", "_")) and (p / "SKILL.md").is_file()]
    if not skills:
        raise InstallError(f"No skill packages found in {skills_dir}")
    for skill in skills:
        checked_path(skill)
        for path in sorted(skill.rglob("*")):
            # Portable skills can include Python helpers; importing them during
            # local validation must not turn interpreter caches into package files.
            if "__pycache__" in path.relative_to(skill).parts or path.suffix in {".pyc", ".pyo"}:
                continue
            checked_path(path)
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def extract_block(soul: bytes) -> bytes | None:
    if START not in soul and END not in soul:
        return None
    if soul.count(START) != 1 or soul.count(END) != 1:
        raise InstallError("SOUL.md has missing or duplicate managed block markers")
    start = soul.index(START)
    end = soul.index(END) + len(END)
    if end <= start:
        raise InstallError("SOUL.md has reversed managed block markers")
    return soul[start:end]


def desired_block(home: Path, instructions: bytes) -> bytes:
    try:
        policy = instructions.decode("utf-8-sig").strip()
    except UnicodeError as exc:
        raise InstallError("instructions.md must contain UTF-8 text") from exc
    links = (
        "\n\nLoad the installed capability registry and relevant workflow contract when needed:\n"
        f"- Capability registry: `{(home / OWNER / 'capabilities.json').as_posix()}`\n"
        f"- Workflow contracts: `{(home / OWNER / 'workflow-contracts.md').as_posix()}`\n"
        f"- Setup and editable connections/routing: `{(home / OWNER / 'setup-contract.md').as_posix()}`\n"
        f"- Settings tool: `{(home / OWNER / 'settings.py').as_posix()}`; use --hermes-home `{home.as_posix()}` and JSON on stdin.\n"
        "These paths describe capabilities; confirm actual tool availability and results.\n"
    )
    return START + b"\n" + (policy + links).encode("utf-8") + END


def load_state(home: Path) -> tuple[dict, bytes | None]:
    raw = read_optional(target_path(home, STATE_PATH))
    if raw is None:
        return {"schema_version": 1, "files": {}, "soul_block_sha256": None}, None
    try:
        state = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise InstallError("Invalid installation state; preserve it and reconcile manually") from exc
    if (not isinstance(state, dict) or state.get("schema_version") != 1
            or not isinstance(state.get("files"), dict)
            or not isinstance(state.get("soul_block_sha256"), str)):
        raise InstallError("Unsupported installation state; preserve it and reconcile manually")
    for relative, fingerprint in state["files"].items():
        if (not isinstance(relative, str) or not relative.startswith(("skills/", f"{OWNER}/"))
                or relative == STATE_PATH or not isinstance(fingerprint, str)
                or len(fingerprint) != 64):
            raise InstallError("Invalid owned file entry in installation state")
        target_path(home, relative)
    return state, raw


def build_plan(root: Path, home: Path) -> dict:
    root, home = checked_path(root), checked_path(home)
    source_trees = (root / "skills", root / "components" / "hermes-orchestration")
    if root.is_relative_to(home) or any(
        home.is_relative_to(tree) or tree.is_relative_to(home) for tree in source_trees
    ):
        raise InstallError("Source and target must not overlap; choose a profile outside the source trees")
    if home.exists() and not home.is_dir():
        raise InstallError(f"Hermes home must be a directory: {home}")
    desired = collect_sources(root)
    state, state_before = load_state(home)
    changes, before, conflicts = {}, {}, []
    for relative, content in desired.items():
        current = read_optional(target_path(home, relative))
        before[relative] = current
        if current == content:
            continue
        if current is not None and digest(current) != state["files"].get(relative):
            conflicts.append(f"{relative}: existing content is unowned or locally edited")
        else:
            changes[relative] = content
    for relative in state["files"]:
        if relative not in desired:
            parts = PurePosixPath(relative).parts
            if len(parts) >= 3 and parts[0] == "skills" and parts[1] in RETIRED_SKILLS:
                current = read_optional(target_path(home, relative))
                before[relative] = current
                if current is not None and digest(current) != state["files"][relative]:
                    conflicts.append(f"{relative}: retired skill is locally edited; preserve and reconcile it")
                elif current is not None:
                    changes[relative] = None  # Explicit package retirement; backed up before removal.
            else:
                conflicts.append(f"{relative}: removed from source; an explicit migration is required")
    for name in RETIRED_SKILLS:
        entry = f"skills/{name}/SKILL.md"
        if entry not in desired and entry not in state["files"] and read_optional(target_path(home, entry)) is not None:
            conflicts.append(f"{entry}: retired skill is unowned; preserve and reconcile it before installing")

    soul = read_optional(target_path(home, "SOUL.md"))
    before["SOUL.md"] = soul
    current_block = extract_block(soul or b"")
    block = desired_block(home, desired[f"{OWNER}/instructions.md"])
    previous_hash = state.get("soul_block_sha256")
    if current_block is not None and current_block != block and digest(current_block) != previous_hash:
        conflicts.append("SOUL.md: managed block is unowned or locally edited")
    elif current_block is None and previous_hash is not None:
        conflicts.append("SOUL.md: previously installed managed block is missing")
    elif current_block != block:
        if current_block is None:
            prefix = soul if soul is not None else b"You are Hermes, a helpful personal AI agent.\n"
            changes["SOUL.md"] = prefix + b"\n\n" + block + b"\n"
        else:
            changes["SOUL.md"] = soul.replace(current_block, block, 1)

    new_state = {
        "schema_version": 1,
        "files": {path: digest(content) for path, content in sorted(desired.items())},
        "soul_block_sha256": digest(block),
    }
    state_content = (json.dumps(new_state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    before[STATE_PATH] = state_before
    if state_content != state_before:
        changes[STATE_PATH] = state_content
    return {"home": home, "changes": changes, "before": before, "conflicts": conflicts,
            "file_count": len(desired), "skill_count": len({p.split('/')[1] for p in desired if p.startswith('skills/')})}


def atomic_write(path: Path, content: bytes, *, expected=UNCHECKED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        if expected is not UNCHECKED and read_optional(checked_path(path)) != expected:
            raise InstallError(f"Changed before replacement: {path}; preserve the edit and rerun preflight")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def installation_lock(home: Path):
    """Serialize installers; this cannot lock out unrelated editors or Hermes."""
    path = target_path(home, LOCK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "token": uuid.uuid4().hex}).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise InstallError(
            f"Installer lock exists: {path}. Another installer may be running. "
            "After an interrupted run, ensure no installer is active, preserve any backups, "
            "then remove only this stale lock and rerun preflight."
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        yield
    finally:
        if read_optional(checked_path(path)) != payload:
            raise InstallError(f"Installer lock changed unexpectedly; left untouched: {path}")
        path.unlink()


def apply_plan(plan: dict) -> Path | None:
    if plan["conflicts"]:
        raise InstallError("Resolve installation conflicts before applying")
    home = plan["home"]
    with installation_lock(home):
        # Recheck the complete inspected surface after obtaining the installer lock.
        for relative, expected in plan["before"].items():
            if read_optional(target_path(home, relative)) != expected:
                raise InstallError(f"Changed since preflight: {relative}; rerun the installer")
        if not plan["changes"]:
            return None
        backup_relative = f"{OWNER}/backups/{uuid.uuid4().hex}"
        backup = target_path(home, backup_relative)
        for relative in plan["changes"]:
            original = plan["before"][relative]
            if original is not None:
                atomic_write(target_path(home, f"{backup_relative}/{relative}"), original, expected=None)
        # Each replacement checks again immediately before os.replace. Unrelated
        # writers are not OS-locked; a small check/replace race still exists.
        for relative, content in plan["changes"].items():
            if relative != STATE_PATH:
                target = target_path(home, relative)
                if content is None:
                    if read_optional(target) != plan["before"][relative]:
                        raise InstallError(f"Changed before removal: {relative}; preserve the edit and rerun preflight")
                    target.unlink()
                else:
                    atomic_write(target, content, expected=plan["before"][relative])
        # Do not record ownership of a mixed or concurrently edited installation.
        for relative, original in plan["before"].items():
            if relative == STATE_PATH:
                continue
            expected = plan["changes"].get(relative, original)
            if read_optional(target_path(home, relative)) != expected:
                raise InstallError(f"Changed before state commit: {relative}; preserve edits and inspect backups")
        if STATE_PATH in plan["changes"]:
            atomic_write(target_path(home, STATE_PATH), plan["changes"][STATE_PATH],
                         expected=plan["before"][STATE_PATH])
        return backup if backup.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", type=Path, required=True,
                        help="Exact active Hermes profile directory; no default is guessed")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply the preflighted installation")
    mode.add_argument("--check", action="store_true", help="Exit 1 if installation differs; never write")
    parser.add_argument("--n8n-url", help="Optional existing instance MCP URL; adds OAuth configuration, never logs in or changes workflows")
    parser.add_argument("--n8n-server-name", default="n8n_larp", help="Name for a new MCP entry, or an explicit choice among matching entries")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(ROOT, args.hermes_home)
        n8n_server = add_n8n_to_plan(plan, args.n8n_url, args.n8n_server_name) if args.n8n_url else None
        print(f"Profile: {plan['home']}")
        print(f"Source: {plan['skill_count']} skills and {len(RESOURCES)} orchestration resources")
        if plan["conflicts"]:
            for conflict in plan["conflicts"]:
                print(f"CONFLICT {conflict}", file=sys.stderr)
            print("No profile changes made.", file=sys.stderr)
            return 2
        for relative in sorted(plan["changes"]):
            operation = "REMOVE" if plan["changes"][relative] is None else "CREATE" if plan["before"][relative] is None else "UPDATE"
            print(f"{operation} {relative}")
        if args.apply:
            backup = apply_plan(plan)
            print("Installed. Start a new Hermes session." if plan["changes"] else "Installation is current.")
            if backup:
                print(f"Replaced-file backup: {backup}")
        elif plan["changes"]:
            print("Check: changes required." if args.check else "Dry run only. Add --apply to install.")
        else:
            print("Installation is current.")
        if n8n_server:
            print(f"Selected MCP connection: {n8n_server}")
            print("MCP configuration checked locally; authentication and workflow access are NOT verified.")
            print(f"Next: run 'hermes mcp login {n8n_server}' in the same active profile (use -p PROFILE for a named profile).")
            print("Then follow components/hermes-orchestration/partner-setup.md for live discovery, route selection and acceptance.")
            print("Model, credentials, speech and remote n8n workflows were not changed.")
        else:
            print("Connections, model, credentials and speech configuration were not changed.")
        return 1 if args.check and plan["changes"] else 0
    except (InstallError, OSError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
