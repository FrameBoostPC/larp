"""Host entry point for planner imports, calendar edits and a bounded sync poll."""
import argparse
import importlib
import json
import os
from pathlib import Path

from planning_sync import Engine


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def validate_output(skill_name, payload, result_file):
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import validate
    if validate.yaml is None or validate.Draft202012Validator is None:
        raise ValueError("Install requirements-dev.txt for workflow output validation")
    errors = []
    schema = validate.load_schema(root / "skills" / skill_name, errors)
    if schema is not None:
        validate.check_instance(schema, payload, Path(result_file), errors)
    if errors or schema is None:
        raise ValueError("; ".join(errors) or "Cannot load workflow schema")


def build_engine(config_path):
    config_file = Path(config_path).resolve()
    config = load_json(config_file)
    db = Path(config["state_path"])
    if not db.is_absolute():
        db = config_file.parent / db
    adapters = []
    if config.get("notion"):
        from notion_adapter import NotionAdapter
        notion = config["notion"]
        env_name = notion.get("token_env", "NOTION_TOKEN")

        def token():
            value = os.environ.get(env_name)
            if not value:
                raise RuntimeError(f"Missing secret environment variable {env_name}")
            return value

        adapters.append(NotionAdapter(notion["data_source_id"], notion["properties"], token,
                                      status_names=notion.get("status_names")))
    if config.get("calendar"):
        from calendar_adapter import CalendarAdapter
        # This is trusted host configuration, never a model output or user task.
        module_name, separator, factory_name = config["calendar"]["client_factory"].partition(":")
        if not separator:
            raise ValueError("calendar.client_factory must be a trusted module:factory")
        factory = getattr(importlib.import_module(module_name), factory_name)
        adapters.append(CalendarAdapter(factory(config["calendar"].get("options", {}))))
    return Engine(db, adapters)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Private host configuration JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sync")
    import_command = sub.add_parser("import-plan")
    import_command.add_argument("--project-id", required=True)
    import_command.add_argument("--request-id", required=True)
    import_command.add_argument("--input", required=True)
    apply_command = sub.add_parser("apply")
    apply_command.add_argument("--request-id", required=True)
    apply_command.add_argument("--input", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--task-id", required=True)
    resolve.add_argument("--revision", required=True, type=int)
    resolve.add_argument("--request-id", required=True)
    resolve.add_argument("--input", required=True, help="JSON patch with explicit conflict choices")
    args = parser.parse_args(argv)
    engine = build_engine(args.config)
    try:
        if args.command == "status":
            result = {"configured_surfaces": list(engine.adapters), "tasks": engine.list_tasks(),
                      "conflicts": {task["id"]: engine.conflicts(task["id"]) for task in engine.list_tasks() if engine.conflicts(task["id"])}}
        elif args.command == "sync":
            if not engine.adapters:
                raise ValueError("No external adapters configured; tasks are saved locally only")
            result = engine.sync()
        elif args.command == "import-plan":
            # Reuse the repository's maintained schema and budget checks.
            # Installed skill folders alone do not include this host component.
            result_file = Path(args.input)
            payload = load_json(result_file)
            validate_output("project-planner", payload, result_file)
            result = engine.import_plan(args.project_id, payload, args.request_id)
        elif args.command == "apply":
            payload = load_json(args.input)
            validate_output("calendar-planner", payload, args.input)
            if payload["data"] is None:
                raise ValueError("No actionable calendar proposal")
            result = engine.apply_operations(payload["data"]["operations"], args.request_id,
                                             project_id=payload["data"]["project_id"])
        else:
            result = engine.resolve_conflict(args.task_id, load_json(args.input), args.revision, args.request_id)
        print(json.dumps(result, indent=2))
        if args.command == "sync" and (result["errors"] or result["conflicts"]):
            return 1
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
