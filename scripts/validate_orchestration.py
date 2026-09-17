#!/usr/bin/env python3
"""Validate the local Hermes capability registry without calling connected tools."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path("components/hermes-orchestration/capabilities.json")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"{value} is not a JSON number")


def validate_registry(root: Path) -> list[str]:
    """Return actionable errors; read only the registry and local skill filenames.

    A registry entry describes a capability, not a live connection. This check
    deliberately makes no network requests and never runs a workflow or model.
    """
    root = Path(root).resolve()
    errors: list[str] = []

    def fail(where: str, message: str) -> None:
        errors.append(f"{REGISTRY_PATH.as_posix()}: {where}: {message}")

    def nonempty(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def require_fields(obj: dict, fields: tuple[str, ...], where: str) -> None:
        for field in fields:
            if field not in obj:
                fail(where, f"missing required field {field!r}")

    def string_list(value: object, where: str, *, allow_empty: bool = False) -> list[str]:
        if not isinstance(value, list):
            fail(where, "must be an array of nonempty strings")
            return []
        if not value and not allow_empty:
            fail(where, "must contain at least one string")
        valid = []
        seen = set()
        for index, item in enumerate(value):
            if not nonempty(item):
                fail(f"{where}[{index}]", "must be a nonempty string")
            elif item in seen:
                fail(where, f"duplicate value {item!r}")
            else:
                valid.append(item)
                seen.add(item)
        return valid

    def objects(value: object, where: str, *, allow_empty: bool = False) -> list[tuple[int, dict]]:
        if not isinstance(value, list):
            fail(where, "must be an array of objects")
            return []
        if not value and not allow_empty:
            fail(where, "must contain at least one object")
        result = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                fail(f"{where}[{index}]", "must be an object")
            else:
                result.append((index, item))
        return result

    def unique_id(value: object, where: str, seen: set[str], *, slug: bool = True) -> str | None:
        if not nonempty(value) or (slug and not SLUG.fullmatch(value)):
            fail(where, "must be a lowercase hyphenated identifier" if slug else "must be a nonempty string")
            return None
        if value in seen:
            fail(where, f"duplicate identifier {value!r}")
        seen.add(value)
        return value

    path = root / REGISTRY_PATH
    try:
        if not path.resolve().is_relative_to(root):
            fail("registry", "path escapes the project root")
            return errors
        registry = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        fail("registry", f"cannot read valid JSON ({exc})")
        return errors

    if not isinstance(registry, dict):
        fail("registry", "must be an object")
        return errors
    require_fields(registry, (
        "schema_version", "orchestrator", "observed_at", "n8n_instance",
        "interaction", "skills", "features", "workflows",
    ), "registry")
    if registry.get("schema_version") != "1.0":
        fail("schema_version", "must be '1.0'")
    if registry.get("orchestrator") != "hermes":
        fail("orchestrator", "must be 'hermes'")

    observed = registry.get("observed_at")
    try:
        if not isinstance(observed, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed):
            raise ValueError("expected YYYY-MM-DD")
        date.fromisoformat(observed)
    except ValueError:
        fail("observed_at", "must be a valid ISO date (YYYY-MM-DD)")

    instance = registry.get("n8n_instance")
    try:
        if not isinstance(instance, str) or re.search(r"\s", instance):
            raise ValueError("expected URL")
        url = urlsplit(instance)
        if (
            url.scheme != "https" or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", url.hostname)
            or any(not label for label in url.hostname.split("."))
        ):
            raise ValueError("invalid instance URL")
        _ = url.port  # Parse the port too: malformed or out-of-range ports are invalid.
    except ValueError:
        fail("n8n_instance", "must be an HTTPS instance URL without credentials, query or fragment")

    interaction = registry.get("interaction")
    if not isinstance(interaction, dict):
        fail("interaction", "must be an object")
    else:
        primary = string_list(interaction.get("primary"), "interaction.primary")
        if set(primary) != {"voice", "text"}:
            fail("interaction.primary", "must contain voice and text")
        for flag in ("final_transcripts_only", "shared_state", "concise_spoken_results"):
            if interaction.get(flag) is not True:
                fail(f"interaction.{flag}", "must be true")

    skill_ids: set[str] = set()
    for index, skill in objects(registry.get("skills"), "skills"):
        where = f"skills[{index}]"
        require_fields(skill, ("id", "label"), where)
        unique_id(skill.get("id"), f"{where}.id", skill_ids)
        if not nonempty(skill.get("label")):
            fail(f"{where}.label", "must be a nonempty string")

    installed_skills: set[str] = set()
    skill_root = root / "skills"
    try:
        if not skill_root.resolve().is_relative_to(root):
            fail("skills", "skill directory escapes the project root")
        else:
            for folder in skill_root.iterdir():
                # Do not follow linked packages into another project or private storage.
                if folder.is_symlink():
                    fail("skills", f"linked package {folder.name!r} cannot be inventoried")
                    continue
                entry = folder / "SKILL.md"
                if not entry.resolve().is_relative_to(root):
                    fail("skills", f"package {folder.name!r} escapes the project root")
                elif folder.is_dir() and entry.is_file():
                    installed_skills.add(folder.name)
    except OSError as exc:
        fail("skills", f"cannot inventory local packages ({exc})")
    for missing in sorted(installed_skills - skill_ids):
        fail("skills", f"local package {missing!r} is missing from the registry")
    for nonexistent in sorted(skill_ids - installed_skills):
        fail("skills", f"registered skill {nonexistent!r} has no local SKILL.md")

    workflow_keys: set[str] = set()
    workflow_ids: set[str] = set()
    workflows: dict[str, dict] = {}
    for index, workflow in objects(registry.get("workflows"), "workflows", allow_empty=True):
        where = f"workflows[{index}]"
        require_fields(workflow, (
            "key", "id", "name", "lifecycle", "exposure", "actions", "trigger",
            "terminal_nodes", "production_callable",
        ), where)
        key = unique_id(workflow.get("key"), f"{where}.key", workflow_keys)
        unique_id(workflow.get("id"), f"{where}.id", workflow_ids, slug=False)
        if key is not None:
            workflows[key] = workflow
        if not nonempty(workflow.get("name")):
            fail(f"{where}.name", "must be a nonempty string")
        lifecycle, exposure = workflow.get("lifecycle"), workflow.get("exposure")
        if lifecycle not in ("published", "draft", "archived"):
            fail(f"{where}.lifecycle", "must be published, draft or archived")
        if exposure not in ("direct", "internal", "retired"):
            fail(f"{where}.exposure", "must be direct, internal or retired")
        direct = exposure == "direct"
        string_list(workflow.get("actions"), f"{where}.actions", allow_empty=not direct)
        string_list(workflow.get("terminal_nodes"), f"{where}.terminal_nodes", allow_empty=not direct)
        if direct and workflow.get("trigger") != "Agent request":
            fail(f"{where}.trigger", "direct routes must use 'Agent request'")
        elif not direct and workflow.get("trigger") is not None:
            fail(f"{where}.trigger", "internal and retired routes must not expose a direct trigger")
        if lifecycle == "archived" and exposure != "retired":
            fail(where, "archived workflows must have retired exposure")
        if exposure == "retired" and lifecycle != "archived":
            fail(where, "retired exposure requires an archived workflow")
        expected = lifecycle == "published" and direct
        if not isinstance(workflow.get("production_callable"), bool):
            fail(f"{where}.production_callable", "must be a boolean")
        elif workflow["production_callable"] != expected:
            fail(f"{where}.production_callable", "must be true exactly for published direct workflows")

    feature_ids: set[str] = set()
    for index, feature in objects(registry.get("features"), "features"):
        where = f"features[{index}]"
        require_fields(feature, (
            "id", "label", "skill_id", "workflow_key", "tool_roles", "intent_examples", "notes",
        ), where)
        unique_id(feature.get("id"), f"{where}.id", feature_ids)
        for field in ("label", "notes"):
            if not nonempty(feature.get(field)):
                fail(f"{where}.{field}", "must be a nonempty string")
        roles = string_list(feature.get("tool_roles"), f"{where}.tool_roles", allow_empty=True)
        string_list(feature.get("intent_examples"), f"{where}.intent_examples")
        skill, workflow_key = feature.get("skill_id"), feature.get("workflow_key")
        if skill is not None and (not isinstance(skill, str) or skill not in skill_ids):
            fail(f"{where}.skill_id", "must reference a registered skill or be null")
        if workflow_key is not None:
            if not isinstance(workflow_key, str) or workflow_key not in workflows:
                fail(f"{where}.workflow_key", "must reference a registered workflow or be null")
            elif workflows[workflow_key].get("exposure") != "direct":
                fail(f"{where}.workflow_key", "features must not directly route to internal or retired workflows")
        if skill is None and workflow_key is None and not roles:
            fail(where, "must select a skill, direct workflow or connected tool role")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT, help="project root (defaults to this repository)")
    args = parser.parse_args(argv)
    errors = validate_registry(args.root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Hermes capability registry is valid (offline contract checks only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
