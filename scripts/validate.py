#!/usr/bin/env python3
"""Validate skill packages or a generated JSON response without executing skills."""

from __future__ import annotations

import argparse
import json
import re
import runpy
import sys
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
except ImportError:
    yaml = None
    Draft202012Validator = None
    FormatChecker = None
    SchemaError = None


ROOT = Path(__file__).resolve().parents[1]
MISSING = object()
ENVELOPE_FIELDS = {
    "schema_version", "skill", "status", "title", "summary", "assumptions",
    "questions", "limitations", "data",
}
SEMVER = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
REFERENCE_LINK = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|(\S+))", re.MULTILINE)


def label(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label(path)}: cannot read file ({exc})")
        return None


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> None:
    raise ValueError(f"{value} is not a JSON number")


def read_json(path: Path, errors: list[str]):
    text = read_text(path, errors)
    if text is None:
        return MISSING
    try:
        return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_nonfinite)
    except ValueError as exc:
        errors.append(f"{label(path)}: invalid JSON ({exc})")
        return MISSING


def check_frontmatter(path: Path, skill_name: str, errors: list[str]) -> None:
    text = read_text(path, errors)
    if text is None:
        return
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        errors.append(f"{label(path)}: must start with YAML frontmatter between --- lines")
        return
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{label(path)}: invalid YAML frontmatter ({exc})")
        return
    if not isinstance(frontmatter, dict):
        errors.append(f"{label(path)}: frontmatter must be a mapping")
        return
    if frontmatter.get("name") != skill_name:
        errors.append(f"{label(path)}: name must match folder {skill_name!r}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name) or len(skill_name) > 64:
        errors.append(f"{label(path)}: folder name must be 1–64 lowercase letters, digits, and single hyphens")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append(f"{label(path)}: description must be a nonempty string of at most 1024 characters")
    metadata = frontmatter.get("metadata")
    version = metadata.get("version") if isinstance(metadata, dict) else None
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append(f"{label(path)}: metadata.version must be a quoted semantic version such as '0.1.0'")


def prose_only(text: str) -> str:
    """Exclude code fences and inline code, which can contain illustrative links."""
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        lines.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(lines))


def check_links(skill_dir: Path, errors: list[str]) -> None:
    boundary = skill_dir.resolve()
    for path in sorted(skill_dir.rglob("*.md")):
        text = read_text(path, errors)
        if text is None:
            continue
        prose = prose_only(text)
        for pattern in (INLINE_LINK, REFERENCE_LINK):
            for match in pattern.finditer(prose):
                target = match[1] or match[2]
                try:
                    parsed = urlsplit(target)
                except ValueError:
                    errors.append(f"{label(path)}: malformed link {target!r}")
                    continue
                if target.startswith("//") or (parsed.scheme and parsed.scheme != "file" and not re.match(r"^[A-Za-z]:", target)):
                    continue
                if not parsed.path and not parsed.scheme:
                    continue  # A link to a heading in this document.
                local_path = unquote(parsed.path).replace("\\", "/")
                if parsed.scheme or local_path.startswith("/") or re.match(r"^[A-Za-z]:", local_path):
                    errors.append(f"{label(path)}: local link must be relative to its skill folder: {target!r}")
                    continue
                resolved = (path.parent / local_path).resolve()
                if not resolved.is_relative_to(boundary):
                    errors.append(f"{label(path)}: link escapes skill folder: {target!r}")
                elif not resolved.exists():
                    errors.append(f"{label(path)}: missing linked resource: {target!r}")


def check_refs(node, path: Path, errors: list[str]) -> None:
    """Keep validation offline: schemas must bundle all referenced definitions."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(value, str) and not value.startswith("#"):
                errors.append(f"{label(path)}: schema references must be internal fragments; found {value!r}")
            check_refs(value, path, errors)
    elif isinstance(node, list):
        for item in node:
            check_refs(item, path, errors)


def load_schema(skill_dir: Path, errors: list[str]):
    path = skill_dir / "templates" / "output.schema.json"
    before = len(errors)
    schema = read_json(path, errors)
    if schema is MISSING:
        return None
    if not isinstance(schema, dict):
        errors.append(f"{label(path)}: schema must be a JSON object")
        return None
    dialect = schema.get("$schema")
    if not isinstance(dialect, str) or dialect.rstrip("#") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(f"{label(path)}: declare the JSON Schema Draft 2020-12 dialect")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        errors.append(f"{label(path)}: invalid JSON Schema ({exc.message})")
        return None
    check_refs(schema, path, errors)
    required = set(schema.get("required", []))
    missing = sorted(ENVELOPE_FIELDS - required)
    if missing:
        errors.append(f"{label(path)}: envelope fields must be required: {', '.join(missing)}")
    properties = schema.get("properties", {})
    skill_property = properties.get("skill", {})
    version_property = properties.get("schema_version", {})
    if not isinstance(skill_property, dict) or skill_property.get("const") != skill_dir.name:
        errors.append(f"{label(path)}: properties.skill.const must be {skill_dir.name!r}")
    legacy_version = isinstance(version_property, dict) and version_property.get("const") == "1.0"
    planning_versions = (skill_dir.name in {"project-planner", "calendar-planner"}
                         and isinstance(version_property, dict)
                         and version_property.get("enum") == ["1.0", "1.1"])
    if not (legacy_version or planning_versions):
        errors.append(f"{label(path)}: schema_version must declare 1.0, or the supported planning versions ['1.0', '1.1']")
    if len(errors) != before:
        return None
    return schema


def check_instance(schema: dict, data, path: Path, errors: list[str]) -> None:
    try:
        failures = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except Exception as exc:
        # Malformed fragment references can be valid schema syntax but fail to resolve.
        errors.append(f"{label(path)}: schema evaluation failed ({exc})")
        return
    for failure in failures[:12]:
        errors.append(f"{label(path)}: {failure.json_path}: {failure.message}")
    if len(failures) > 12:
        errors.append(f"{label(path)}: {len(failures) - 12} more schema validation errors")
    if not failures:
        check_semantics(data, path, errors)


def index_ids(items: list[dict], field: str, path: Path, errors: list[str]) -> dict[str, dict]:
    indexed = {}
    for index, item in enumerate(items):
        item_id = item["id"]
        if item_id in indexed:
            errors.append(f"{label(path)}: $.data.{field}[{index}].id: duplicate ID {item_id!r}")
        else:
            indexed[item_id] = item
    return indexed


def check_semantics(output: dict, path: Path, errors: list[str]) -> None:
    """Check selected relationships JSON Schema cannot express, after shape validation."""
    data = output.get("data")
    if data is None:
        return
    prefix = f"{label(path)}: $.data"
    if output["skill"] == "idea-to-content":
        hooks = index_ids(data["hooks"], "hooks", path, errors)
        index_ids(data["assets"], "assets", path, errors)
        for index, asset in enumerate(data["assets"]):
            if asset["hook_id"] is not None and asset["hook_id"] not in hooks:
                errors.append(f"{prefix}.assets[{index}].hook_id: unknown hook {asset['hook_id']!r}")
    elif output["skill"] == "project-planner":
        check_plan(data, path, errors, version=output["schema_version"], status=output["status"])
    elif output["skill"] == "calendar-planner":
        check_calendar(data, path, errors)
    if output["skill"] in {"project-planner", "calendar-planner"} and data.get("calendar_review") is not None:
        check_calendar_review(data["calendar_review"], output["status"], path, errors)


def check_calendar_review(review: dict, status: str, path: Path, errors: list[str]) -> None:
    """Check reported arithmetic and bounds, without pretending to verify live sources."""
    prefix = f"{label(path)}: $.data.calendar_review"
    if review["status"] in {"partial", "unavailable"} and status == "ready":
        errors.append(f"{prefix}.status: incomplete requested calendar review requires a partial result")
    available, effort, shortage = (review[key] for key in ("available_minutes", "unscheduled_effort_minutes", "shortfall_minutes"))
    if available is not None and effort is not None:
        expected = max(0, effort - available)
        if shortage != expected:
            errors.append(f"{prefix}.shortfall_minutes: must equal max(0, unscheduled effort minus available capacity)")
        if expected > 0 and status == "ready":
            errors.append(f"{prefix}.shortfall_minutes: a capacity shortage requires a partial result")
    elif shortage is not None:
        errors.append(f"{prefix}.shortfall_minutes: unknown effort or availability requires an unknown shortage")
    zone = None
    if review["timezone"] is not None:
        try:
            zone = ZoneInfo(review["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"{prefix}.timezone: unknown IANA timezone or missing tzdata")
    windows: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for index, window in enumerate(review["working_windows"]):
        start, end = (int(window[key][:2]) * 60 + int(window[key][3:]) for key in ("start", "end"))
        if end <= start:
            errors.append(f"{prefix}.working_windows[{index}]: end must be after start within the same day")
        windows[window["weekday"]].append((start, end))
    for weekday, slots in windows.items():
        latest_end = -1
        for start, end in sorted(slots):
            if start < latest_end:
                errors.append(f"{prefix}.working_windows: overlapping windows on weekday {weekday}")
            latest_end = max(latest_end, end)
    start_date, end_date = review["window_start"], review["window_end"]
    if start_date is not None and end_date is not None:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if end < start:
            errors.append(f"{prefix}.window_end: review window ends before it starts")
        elif available is not None and review["buffer_minutes"] is not None:
            # An upper bound only: real busy intervals must still be checked by the host.
            net_window_minutes = 0
            for weekday, slots in windows.items():
                offset = (weekday - start.isoweekday()) % 7
                if offset > (end - start).days:
                    continue
                cursor = start + timedelta(days=offset)
                while cursor <= end:
                    midnight = datetime.combine(cursor, datetime.min.time(), tzinfo=zone)
                    for left, right in slots:
                        duration = right - left
                        if zone is not None:
                            duration = ((midnight + timedelta(minutes=right)).timestamp()
                                        - (midnight + timedelta(minutes=left)).timestamp()) / 60
                        net_window_minutes += max(0, duration - review["buffer_minutes"])
                    if (end - cursor).days < 7:
                        break
                    cursor += timedelta(days=7)
            allocated = review["already_allocated_minutes"] or 0
            if available + allocated > net_window_minutes:
                errors.append(f"{prefix}.available_minutes: available plus allocated time exceeds working windows after buffers")


def check_calendar(data: dict, path: Path, errors: list[str]) -> None:
    """Validate a proposal without claiming access to current task/calendar state."""
    prefix = f"{label(path)}: $.data.operations"
    seen = set()
    slots = []
    for index, operation in enumerate(data["operations"]):
        location = f"{prefix}[{index}]"
        task_id = operation["task_id"]
        if task_id in seen:
            errors.append(f"{location}.task_id: duplicate task operation; refresh its revision between changes")
        seen.add(task_id)
        if task_id in operation["patch"].get("depends_on", []):
            errors.append(f"{location}.patch.depends_on: task cannot depend on itself")
        schedule = operation["patch"].get("schedule")
        if schedule is None:
            continue
        if operation["patch"].get("status") in {"completed", "cancelled"}:
            errors.append(f"{location}.patch.schedule: completed/cancelled task cannot have an active schedule")
        try:
            zone = ZoneInfo(schedule["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"{location}.patch.schedule.timezone: unknown IANA timezone or missing tzdata")
            continue
        before = len(errors)
        instants = []
        for field in ("start", "end"):
            try:
                instant = datetime.fromisoformat(schedule[field].replace("Z", "+00:00").replace("z", "+00:00"))
            except ValueError:
                errors.append(f"{location}.patch.schedule.{field}: unsupported calendar timestamp")
                continue
            if instant.utcoffset() is None:
                errors.append(f"{location}.patch.schedule.{field}: an explicit UTC offset is required")
                continue
            local = instant.astimezone(zone)
            if local.utcoffset() != instant.utcoffset() or local.replace(tzinfo=None) != instant.replace(tzinfo=None):
                errors.append(f"{location}.patch.schedule.{field}: timestamp offset/local time does not match timezone")
            instants.append(instant)
        if len(instants) != 2:
            continue
        start, end = instants
        if end <= start:
            errors.append(f"{location}.patch.schedule.end: end must be after start")
        if len(errors) == before:
            slots.append((start, end, index))
    # Actual availability and unchanged event slots are checked by the host at execution.
    slots.sort(key=lambda slot: slot[0])
    latest_end = None
    latest_index = None
    for start, end, index in slots:
        if latest_end is not None and start < latest_end:
            errors.append(f"{prefix}[{index}].patch.schedule: overlaps operation {latest_index}")
        if latest_end is None or end > latest_end:
            latest_end, latest_index = end, index


def check_plan(data: dict, path: Path, errors: list[str], *, version: str = "1.0", status: str = "ready") -> None:
    prefix = f"{label(path)}: $.data"
    milestones = index_ids(data["milestones"], "milestones", path, errors)
    tasks = index_ids(data["tasks"], "tasks", path, errors)
    weekly_minutes: dict[int, int] = defaultdict(int)
    positions = {task["id"]: index for index, task in enumerate(data["tasks"])}
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors = {task_id: set() for task_id in tasks}
    for index, task in enumerate(data["tasks"]):
        task_prefix = f"{prefix}.tasks[{index}]"
        if task["estimated_minutes"] is not None:
            weekly_minutes[task["week"]] += task["estimated_minutes"]
        horizon = data.get("horizon_weeks")
        if horizon is not None and task["week"] > horizon:
            errors.append(f"{task_prefix}.week: task is outside the planning horizon")
        if task["milestone_id"] not in milestones:
            errors.append(f"{task_prefix}.milestone_id: unknown milestone {task['milestone_id']!r}")
        elif (target_week := milestones[task["milestone_id"]].get("target_week")) is not None and task["week"] > target_week:
            errors.append(f"{task_prefix}.week: task is later than its milestone target week")
        for dependency in task["depends_on"]:
            if dependency not in tasks:
                errors.append(f"{task_prefix}.depends_on: unknown task {dependency!r}")
                continue
            if dependency == task["id"]:
                errors.append(f"{task_prefix}.depends_on: task cannot depend on itself")
            elif positions[dependency] >= index:
                errors.append(f"{task_prefix}.depends_on: predecessor {dependency!r} must appear before this task")
            if tasks[dependency]["week"] > task["week"]:
                errors.append(f"{task_prefix}.week: predecessor {dependency!r} is scheduled in a later week")
            predecessors[task["id"]].add(dependency)
            successors[dependency].add(task["id"])

    # Iterative topological traversal avoids recursion limits for large generated plans.
    pending = deque(task_id for task_id, dependencies in predecessors.items() if not dependencies)
    visited = 0
    while pending:
        task_id = pending.popleft()
        visited += 1
        for successor in successors[task_id]:
            predecessors[successor].discard(task_id)
            if not predecessors[successor]:
                pending.append(successor)
    if visited < len(tasks):
        errors.append(f"{prefix}.tasks: dependency cycle detected")

    weekly_hours = data["time_budget_hours_per_week"]
    if data.get("planning_mode") == "broad" and data["tasks"] and (weekly_hours == 0 or data["time_budget_minutes_total"] == 0):
        if status != "partial":
            errors.append(f"{prefix}.tasks: a stated zero capacity requires a partial result; required tasks may remain unallocated")
    if weekly_hours is not None and data.get("planning_mode") != "broad":
        budget = Decimal(str(weekly_hours)) * 60
        for week, minutes in sorted(weekly_minutes.items()):
            if minutes > budget:
                if version == "1.0" or status != "partial":
                    suffix = "; version 1.1 requires a partial result with the shortage" if version == "1.1" else ""
                    errors.append(f"{prefix}.tasks: week {week} totals {minutes} minutes, exceeding weekly budget {budget} minutes{suffix}")
    total_budget = data["time_budget_minutes_total"]
    total_minutes = sum(weekly_minutes.values())
    if data.get("planning_mode") != "broad" and total_budget is not None and total_minutes > total_budget:
        if version == "1.0" or status != "partial":
            suffix = "; version 1.1 requires a partial result with the shortage" if version == "1.1" else ""
            errors.append(f"{prefix}.tasks: tasks total {total_minutes} minutes, exceeding total budget {total_budget} minutes{suffix}")

    start, deadline = data["start_date"], data["deadline"]
    # Validated full dates use YYYY-MM-DD, so their lexical and chronological orders agree.
    if start is not None and deadline is not None and deadline < start:
        errors.append(f"{prefix}.deadline: deadline is before start_date")
    if start is not None and deadline is not None:
        for index, task in enumerate(data["tasks"]):
            if (task["week"] - 1) * 7 > (date.fromisoformat(deadline) - date.fromisoformat(start)).days:
                errors.append(f"{prefix}.tasks[{index}].week: task's planning week starts after the deadline")
    for index, milestone in enumerate(data["milestones"]):
        target_week = milestone.get("target_week")
        if target_week is not None and target_week > data["horizon_weeks"]:
            errors.append(f"{prefix}.milestones[{index}].target_week: milestone is outside the planning horizon")
        target = milestone["target_date"]
        if target is None:
            continue
        if start is not None and target < start:
            errors.append(f"{prefix}.milestones[{index}].target_date: target date is before start_date")
        if deadline is not None and target > deadline:
            errors.append(f"{prefix}.milestones[{index}].target_date: target date is after deadline")


def check_cases(path: Path, errors: list[str]) -> int:
    cases = read_json(path, errors)
    if cases is MISSING:
        return 0
    if not isinstance(cases, list) or not cases:
        errors.append(f"{label(path)}: cases must be a nonempty JSON array")
        return 0
    seen = set()
    for index, case in enumerate(cases):
        prefix = f"{label(path)}: case {index + 1}"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{prefix} needs a nonempty string id")
        elif case_id in seen:
            errors.append(f"{prefix} repeats id {case_id!r}")
        else:
            seen.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{prefix} needs a nonempty prompt")
        expected = case.get("expected_behavior")
        if not isinstance(expected, list) or not expected or any(not isinstance(item, str) or not item.strip() for item in expected):
            errors.append(f"{prefix} needs a nonempty expected_behavior array of nonempty strings")
    return len(cases)


def validate_repo(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    passes: list[str] = []
    skills_root = root / "skills"
    skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")) if skills_root.is_dir() else []
    if not skill_dirs:
        errors.append(f"{label(skills_root)}: no skill folders found")
    for skill_dir in skill_dirs:
        before = len(errors)
        check_frontmatter(skill_dir / "SKILL.md", skill_dir.name, errors)
        check_links(skill_dir, errors)
        schema = load_schema(skill_dir, errors)
        example_path = skill_dir / "examples" / "example-output.json"
        example_paths = [example_path] + sorted(path for path in example_path.parent.glob("*.json") if path != example_path)
        for candidate in example_paths:
            example = read_json(candidate, errors)
            if schema is not None and example is not MISSING:
                check_instance(schema, example, candidate, errors)
        count = check_cases(root / "test-cases" / skill_dir.name / "cases.json", errors)
        if len(errors) == before:
            passes.append(f"PASS {skill_dir.name}: package, schema, example, {count} case definitions")
    if (root / "components" / "hermes-orchestration").exists():
        registry_check = runpy.run_path(str(Path(__file__).with_name("validate_orchestration.py")))
        errors.extend(registry_check["validate_registry"](root))
    daily_review = root / "components" / "daily-review"
    if daily_review.exists():
        check_cases(daily_review / "behaviour-cases.json", errors)
    return errors, passes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", nargs=2, metavar=("SKILL", "PATH"), help="validate a generated JSON response against a skill schema")
    args = parser.parse_args(argv)
    if yaml is None or Draft202012Validator is None:
        print("ERROR: validation requires PyYAML and jsonschema.", file=sys.stderr)
        print(f'Install with: "{sys.executable}" -m pip install -r "{ROOT / "requirements-dev.txt"}"', file=sys.stderr)
        return 2
    if args.output:
        skill_name, output_name = args.output
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name):
            parser.error("SKILL must be a skill folder name, for example idea-to-content")
        errors: list[str] = []
        schema = load_schema(ROOT / "skills" / skill_name, errors)
        output_path = Path(output_name).expanduser().resolve()
        data = read_json(output_path, errors)
        if schema is not None and data is not MISSING:
            check_instance(schema, data, output_path, errors)
        passes = [] if errors else [f"PASS {label(output_path)} matches {skill_name}"]
    else:
        errors, passes = validate_repo(ROOT)
    for message in passes:
        print(message)
    for message in errors:
        print(f"ERROR {message}", file=sys.stderr)
    if errors:
        print(f"Validation failed: {len(errors)} error(s).", file=sys.stderr)
        return 1
    if not args.output:
        print(f"Validated {len(passes)} skill package(s). Case definitions were checked; no agent runs were executed.")
        if (ROOT / "components" / "hermes-orchestration").exists():
            print("PASS Hermes capability catalogue: skill coverage, voice contract and workflow routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
