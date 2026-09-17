#!/usr/bin/env python3
"""Profile-local setup and binding plans. No network, OAuth tokens or provider writes.

Hermes supplies discovered metadata, applies returned n8n operations through its
authenticated tools, then verifies the resulting workflow. JSON in/out on stdin.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SettingsError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SettingsError(message)


def identifier(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,199}", value))


def name(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and not any(ord(c) < 32 for c in value) and "{{" not in value


def fields(value, allowed, label):
    require(isinstance(value, dict) and set(value) <= set(allowed), f"Invalid {label} fields")


def fresh():
    return {"schema_version": 1, "revision": 0, "configuration_id": "unconfigured", "instance_url": None,
            "connections": {}, "resources": {}, "routes": {},
            "daily_review": {"time": None, "timezone": None, "email_connection": None,
                             "calendar_resource": None, "workbench_resource": None,
                             "email_review_resource": None, "organisation_resource": None,
            "storage_resource": None}, "preview": None, "deployment": None, "previous_routes": {}, "last_command": None}


def validate(state, catalogue):
    require(state.get("schema_version") == 1 and type(state.get("revision")) is int, "Invalid settings version")
    url = state["instance_url"]
    if url is not None:
        parsed = urlsplit(url)
        require(parsed.scheme == "https" or parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1"), "Use HTTPS, or a local n8n URL")
        require(parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in ("", "/"), "Use an instance origin without credentials")
    for key, connection in state["connections"].items():
        require(identifier(key), "Invalid connection key")
        fields(connection, ("provider", "credential_type", "credential_id", "credential_name", "account_id"), "connection")
        require(all(name(connection.get(k)) for k in ("provider", "credential_name", "account_id")), "Connection needs provider, display name and account identity")
        require(identifier(connection.get("credential_type")) and identifier(connection.get("credential_id")), "Connection needs a discovered credential reference")
    for key, resource in state["resources"].items():
        require(identifier(key), "Invalid resource key")
        fields(resource, ("kind", "resource_id", "label", "connection_key"), "resource")
        require(resource.get("kind") in ("n8n_table", "notion_data_source", "gmail_label", "folder", "calendar"), "Unsupported resource kind")
        require(identifier(resource.get("resource_id")) and name(resource.get("label")), "Resource needs its discovered ID and label")
        require(resource.get("connection_key") is None or resource["connection_key"] in state["connections"], "Resource connection is missing")
    owners = {w["key"]: w for w in catalogue["workflows"]}
    for key, route in state["routes"].items():
        require(key in owners and owners[key]["exposure"] != "retired", "Unknown or retired route")
        fields(route, ("workflow_id", "trigger", "terminal_nodes"), "route")
        require(identifier(route.get("workflow_id")), "Route needs a discovered workflow ID")
        if owners[key]["exposure"] == "direct":
            require(name(route.get("trigger")) and isinstance(route.get("terminal_nodes"), list) and route["terminal_nodes"] and all(name(n) for n in route["terminal_nodes"]), "Direct route needs trigger and terminal nodes")
    daily = state["daily_review"]
    fields(daily, fresh()["daily_review"], "daily review")
    require(set(daily) == set(fresh()["daily_review"]), "Incomplete daily settings object")
    if daily["time"] is not None:
        require(isinstance(daily["time"], str) and bool(re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", daily["time"])), "Daily time must be HH:MM")
    if daily["timezone"] is not None:
        try:
            ZoneInfo(daily["timezone"])
        except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
            raise SettingsError("Timezone must be an installed IANA timezone; Windows Python may need tzdata") from exc
    if daily["email_connection"] is not None:
        require(daily["email_connection"] in state["connections"], "Selected email connection is missing")
        connection = state["connections"][daily["email_connection"]]
        require(connection["provider"] == "gmail" and connection["credential_type"] == "gmailOAuth2", "Daily Review currently supports Gmail")
    for key in ("calendar_resource", "workbench_resource", "email_review_resource", "organisation_resource", "storage_resource"):
        if daily[key] is not None:
            resource = state["resources"].get(daily[key])
            require(resource is not None, f"Selected {key} is missing")
            require(resource["kind"] == ("notion_data_source" if key == "calendar_resource" else "n8n_table"), f"Unsupported {key} adapter")
    require(daily["email_connection"] or not (daily["email_review_resource"] or daily["organisation_resource"]), "Email review/organisation tables require a selected mailbox")
    return state


def status(state):
    d = state["daily_review"]
    missing = []
    for key, value in (("n8n_connection", state["instance_url"]), ("daily_review_route", state["routes"].get("priorities")),
                       ("time", d["time"]), ("timezone", d["timezone"]), ("snapshot_storage", d["storage_resource"])):
        if not value:
            missing.append(key)
    if not any(d[k] for k in ("email_connection", "calendar_resource", "workbench_resource")):
        missing.append("at_least_one_source")
    if d["calendar_resource"] and "calendar" not in state["routes"]:
        missing.append("calendar_route")
    deployed = state.get("deployment") or {}
    current = deployed.get("configuration_id") == state["configuration_id"]
    stage = "setup_required" if missing else "active" if current and deployed.get("active") else "paused" if current and deployed.get("mode") == "paused" else "ready_to_preview"
    return {"status": stage, "missing": missing, "settings": state, "remote_changed": False}


def update(state, changes, catalogue):
    fields(changes, ("instance_url", "connections", "resources", "routes", "daily_review"), "settings patch")
    result = deepcopy(state)
    for key, value in changes.items():
        if key == "instance_url":
            result[key] = value
        elif key == "daily_review":
            fields(value, result[key], "daily review patch")
            result[key].update(value)
        else:
            require(isinstance(value, dict), f"{key} must be an object")
            for entry, selected in value.items():
                if selected is None:
                    result[key].pop(entry, None)
                else:
                    result[key][entry] = selected
    validate(result, catalogue)
    if any(result[k] != state[k] for k in changes):
        result["previous_routes"] = deepcopy(state["routes"])
        result["configuration_id"] = uuid.uuid4().hex
        result["preview"] = None
    return result


def workflow_node(workflow, node_name):
    nodes = [n for n in workflow.get("nodes", []) if n["name"] == node_name]
    require(len(nodes) == 1, f"Missing or ambiguous node: {node_name}")
    return nodes[0]


def unwrap(value):
    return value.get("workflow", value)


def check_workflow(state, route_key, export):
    w = unwrap(export)
    route = state["routes"].get(route_key)
    require(route and w.get("id") == route["workflow_id"], "Workflow does not match the selected route")
    require(not w.get("isArchived") and name(w.get("versionId")), "Need a current unarchived workflow export and version")
    return w


def resolve_route(state, catalogue, key, export):
    require(state["instance_url"], "Select the authenticated n8n connection first")
    owner = next((w for w in catalogue["workflows"] if w["key"] == key), None)
    require(owner and owner["exposure"] == "direct", "Internal/retired routes cannot be dispatched directly")
    w = check_workflow(state, key, export)
    require(w.get("active") is True and w.get("activeVersionId") and w.get("canExecute") is True, "Route is not published and executable")
    graph = w if (w.get("activeVersion") or {}).get("sameAsDraft") else w.get("activeVersion")
    require(graph, "Full published graph required")
    route = state["routes"][key]
    trigger = workflow_node(graph, route["trigger"])
    require(trigger["type"].endswith(".chatTrigger") and not trigger.get("disabled") and trigger.get("parameters", {}).get("public") is False, "Expected a private enabled agent trigger")
    for terminal in route["terminal_nodes"]:
        workflow_node(graph, terminal)
    if key == "priorities":
        config = json.loads(workflow_node(graph, "Review configuration")["parameters"]["jsonOutput"])["review_config"]
        require(config.get("configuration_id") == state["configuration_id"] and config.get("mode") in ("active", "paused"), "Apply and verify the selected recap settings before retrieval")
    return {"status": "ready", "instance_url": state["instance_url"], **route, "actions": owner["actions"], "configuration_id": state["configuration_id"]}


def runtime_configuration(state, mode):
    d = state["daily_review"]
    return {"schema_version": 1, "configuration_id": state["configuration_id"], "mode": mode,
            "time": d["time"], "timezone": d["timezone"],
            "sources": {"email": bool(d["email_connection"]), "workbench": bool(d["workbench_resource"]),
                        "calendar": bool(d["calendar_resource"]), "reviews": bool(d["email_review_resource"]),
                        "organisation": bool(d["organisation_resource"])},
            "labels": {"email": state["connections"].get(d["email_connection"], {}).get("account_id"),
                       "calendar": state["resources"].get(d["calendar_resource"], {}).get("label")}}


def resource_id(state, key):
    return state["resources"][key]["resource_id"]


def calendar_source(graph):
    code = workflow_node(graph, "Scheduling settings")["parameters"].get("jsCode", "")
    matches = re.findall(r'\bdata_source_id\s*:\s*("[^"\\]*")', code)
    require(len(matches) == 1, "Calendar settings adapter does not match this workflow")
    return json.loads(matches[0])


def calendar_binding_plan(state, export):
    """Change the existing calendar owner's central resource and all Notion nodes."""
    w = check_workflow(state, "calendar", export)
    key = state["daily_review"]["calendar_resource"]
    require(key, "Select a calendar resource first")
    resource = state["resources"][key]
    connection = state["connections"].get(resource.get("connection_key"))
    require(connection and connection["provider"] == "notion" and connection["credential_type"] == "notionApi", "Select the Notion connection used by this owner")
    old = calendar_source(w)
    settings = workflow_node(w, "Scheduling settings")
    params = deepcopy(settings["parameters"])
    params["jsCode"] = re.sub(r'(\bdata_source_id\s*:\s*)"[^"\\]*"', lambda m: m[1] + json.dumps(resource["resource_id"]), params["jsCode"], count=1)
    operations = [{"type": "updateNodeParameters", "nodeName": settings["name"], "parameters": params}]
    for node in w["nodes"]:
        if node["type"] == "n8n-nodes-base.notion":
            require("notionApi" in node.get("credentials", {}), "Calendar credential adapter changed")
            operations.append({"type": "setNodeCredential", "nodeName": node["name"], "credentialKey": "notionApi",
                               "credentialId": connection["credential_id"], "credentialName": connection["credential_name"]})
    return {"workflow_id": w["id"], "expected_version_id": w["versionId"], "operations": operations, "publish": False,
            "previous_resource_id": old, "selected_resource_id": resource["resource_id"],
            "requires_owner_acceptance": True, "note": "Affects calendar reads and writes and every caller of this calendar owner, including the project planner. Does not move existing pages. Validate the destination Schedule & Tasks schema and test before publishing."}


def binding_plan(state, catalogue, route_key, export, edits):
    """Plan explicit discovered node bindings; never edit code, triggers or send rules."""
    w = check_workflow(state, route_key, export)
    require(isinstance(edits, list) and 0 < len(edits) <= 50, "Provide 1–50 explicit binding edits")
    operations, parameters, impacts = [], {}, []
    for edit in edits:
        fields(edit, ("node", "connection_key", "resource_key", "parameter_path"), "binding edit")
        node = workflow_node(w, edit.get("node"))
        require(("connection_key" in edit) != ("resource_key" in edit), "Choose one connection or resource per edit")
        if "connection_key" in edit:
            connection = state["connections"].get(edit["connection_key"])
            require(connection is not None, "Unknown connection")
            require(connection["credential_type"] in node.get("credentials", {}), "Credential type is not owned by this node")
            operations.append({"type": "setNodeCredential", "nodeName": node["name"], "credentialKey": connection["credential_type"],
                               "credentialId": connection["credential_id"], "credentialName": connection["credential_name"]})
        else:
            resource = state["resources"].get(edit["resource_key"])
            require(resource is not None, "Unknown resource")
            path = edit.get("parameter_path")
            require(isinstance(path, list) and 1 <= len(path) <= 4 and all(isinstance(k, str) for k in path), "A discovered parameter path is required")
            require(path[-1] in ("databaseId", "dataSourceId", "dataTableId", "folderId", "calendarId", "labelIds"), "Only linked-resource parameters may change")
            params = parameters.setdefault(node["name"], deepcopy(node["parameters"]))
            parent = params
            for part in path[:-1]:
                require(isinstance(parent.get(part), dict), "Parameter path is not present")
                parent = parent[part]
            require(path[-1] in parent, "Resource parameter is not present")
            old = parent[path[-1]]
            value = resource["resource_id"]
            parent[path[-1]] = {"__rl": True, "mode": "id", "value": value} if isinstance(old, dict) and old.get("__rl") else [value] if isinstance(old, list) else value
        impacts.append(node["name"])
    operations.extend({"type": "updateNodeParameters", "nodeName": node, "parameters": params} for node, params in parameters.items())
    return {"workflow_id": w["id"], "expected_version_id": w["versionId"], "operations": operations,
            "publish": False, "affected_nodes": sorted(set(impacts)), "requires_owner_acceptance": True,
            "note": "This changes the selected operation owner's bindings only. Confirm affected consumers and test the owner before publication. Email push also needs its mailbox/watch configuration reconciled; credential edits alone do not switch its mailbox."}


def daily_plan(state, export, mode="preview", calendar_export=None):
    require(mode in ("setup_required", "preview", "active", "paused"), "Unknown deployment mode")
    if mode in ("preview", "active"):
        require(not status(state)["missing"], "Finish the selected setup fields before preparing a deployment")
    w = check_workflow(state, "priorities", export)
    workflow_node(w, "Review configuration")
    d = state["daily_review"]
    if mode in ("setup_required", "paused"):
        # Suspension/disconnection must work even after a required source is removed.
        p = deepcopy(workflow_node(w, "Review configuration")["parameters"])
        p["jsonOutput"] = json.dumps({"review_config": runtime_configuration(state, mode)}, separators=(",", ":"))
        return {"workflow_id": w["id"], "expected_version_id": w["versionId"], "configuration_id": state["configuration_id"],
                "mode": mode, "publish": True, "remote_changed": False, "requires_pause_before_change": bool(w.get("active")),
                "operations": [{"type": "updateNodeParameters", "nodeName": "Review configuration", "parameters": p},
                               {"type": "setNodeDisabled", "nodeName": "Daily preparation time", "disabled": True}]}
    if mode == "active":
        require((state.get("preview") or {}).get("configuration_id") == state["configuration_id"], "A successful live preview of this configuration is required")
    if d["calendar_resource"]:
        require(calendar_export is not None, "Read the selected calendar owner to verify its resource binding")
        owner = check_workflow(state, "calendar", calendar_export)
        require(owner.get("active") and owner.get("activeVersionId"), "Selected calendar owner is unpublished")
        graph = owner if (owner.get("activeVersion") or {}).get("sameAsDraft") else owner.get("activeVersion")
        require(graph and any("daily_review_context" in n.get("parameters", {}).get("jsCode", "") for n in graph.get("nodes", [])), "Published calendar owner lacks daily_review_context")
        source = state["resources"][d["calendar_resource"]]
        connection = state["connections"].get(source.get("connection_key"))
        require(connection and connection["provider"] == "notion", "Calendar resource needs its Notion connection")
        readers = [n for n in graph["nodes"] if n["name"] in ("Read Notion schedule", "Read Notion schedule schema")]
        require(len(readers) == 2, "Calendar adapter needs its known read/schema nodes")
        for n in readers:
            require(any(c.get("id") == connection["credential_id"] for c in n.get("credentials", {}).values()), "Calendar owner is linked to a different account; change/test that owner first")
            selected = n["parameters"].get("dataSourceId", {}).get("value")
            if isinstance(selected, str) and selected.startswith("="):
                require(selected == '={{ $("Scheduling settings").first().json.settings.data_source_id }}', "Unknown calendar resource expression")
                selected = calendar_source(graph)
            require(selected == source["resource_id"], "Calendar owner is linked to a different resource; change/test that owner first")
    config = runtime_configuration(state, mode)
    operations = []
    def params(node_name, **changed):
        p = deepcopy(workflow_node(w, node_name)["parameters"])
        p.update(changed)
        operations.append({"type": "updateNodeParameters", "nodeName": node_name, "parameters": p})
    params("Review configuration", jsonOutput=json.dumps({"review_config": config}, separators=(",", ":")))
    hour, minute = map(int, d["time"].split(":"))
    params("Daily preparation time", rule={"interval": [{"field": "days", "daysInterval": 1, "triggerAtHour": hour, "triggerAtMinute": minute}]})
    operations += [{"type": "setNodeDisabled", "nodeName": "Daily preparation time", "disabled": mode != "active"},
                   {"type": "setWorkflowSettings", "settings": {"timezone": d["timezone"]}}]
    storage = resource_id(state, d["storage_resource"])
    table_nodes = {"Read last complete snapshot": storage, "Read latest prepared snapshot": storage, "Save daily review snapshot": storage}
    for field, node_name in (("workbench_resource", "Read pending work"), ("email_review_resource", "Read pending email review"), ("organisation_resource", "Read organisation receipts")):
        if d[field]:
            table_nodes[node_name] = resource_id(state, d[field])
    for node_name, value in table_nodes.items():
        params(node_name, dataTableId={"__rl": True, "mode": "id", "value": value})
    if d["email_connection"]:
        c = state["connections"][d["email_connection"]]
        for node_name in ("Read incoming email", "Check recent spam", "Read recent sent context", "Read existing reply drafts"):
            workflow_node(w, node_name)
            operations.append({"type": "setNodeCredential", "nodeName": node_name, "credentialKey": "gmailOAuth2", "credentialId": c["credential_id"], "credentialName": c["credential_name"]})
    if d["calendar_resource"]:
        params("Read connected calendar", workflowId={"__rl": True, "mode": "id", "value": state["routes"]["calendar"]["workflow_id"]})
    return {"workflow_id": w["id"], "expected_version_id": w["versionId"], "configuration_id": state["configuration_id"],
            "mode": mode, "operations": operations, "publish": mode in ("active", "paused"), "remote_changed": False,
            "preview_trigger": "Run manually", "requires_pause_before_change": bool(w.get("active"))}


def verify_applied(state, export, mode, calendar_export=None):
    w = check_workflow(state, "priorities", export)
    # Rebuild expected operations against fresh metadata and compare actual values.
    expected = daily_plan(state, w, mode, calendar_export)
    if mode in ("active", "preview") and state["daily_review"]["calendar_resource"]:
        require(workflow_node(w, "Read connected calendar")["parameters"]["workflowId"]["value"] == state["routes"]["calendar"]["workflow_id"], "Calendar route was not applied")
    for operation in expected["operations"]:
        kind = operation["type"]
        if kind == "setWorkflowSettings":
            require(all(w.get("settings", {}).get(k) == v for k, v in operation["settings"].items()), "Workflow settings were not applied")
            continue
        node = workflow_node(w, operation["nodeName"])
        if kind == "updateNodeParameters":
            require(node["parameters"] == operation["parameters"], f"Binding was not applied: {node['name']}")
        elif kind == "setNodeDisabled":
            require(bool(node.get("disabled")) == operation["disabled"], "Schedule state was not applied")
        elif kind == "setNodeCredential":
            require(node.get("credentials", {}).get(operation["credentialKey"], {}).get("id") == operation["credentialId"], "Email credential was not applied")
    if mode in ("active", "paused", "setup_required"):
        require(w.get("active") and w.get("activeVersionId") == w.get("versionId"), "The verified draft is not the published version")
    return {"configuration_id": state["configuration_id"], "workflow_id": w["id"], "version_id": w["versionId"], "active": mode == "active", "mode": mode}


def accept_preview(state, evidence):
    fields(evidence, ("workflow_id", "execution_id", "configuration_id", "collection_status", "coverage", "provider_reads"), "preview evidence")
    require(evidence.get("workflow_id") == state["routes"].get("priorities", {}).get("workflow_id") and evidence.get("configuration_id") == state["configuration_id"], "Preview belongs to different bindings")
    require(identifier(evidence.get("execution_id")) and evidence.get("collection_status") == "complete" and evidence.get("provider_reads") == "live", "Preview needs a complete live collection, not a pinned fixture")
    required = {"work": "workbench_resource", "calendar": "calendar_resource", "reviews": "email_review_resource", "organisation": "organisation_resource"}
    if state["daily_review"]["email_connection"]:
        required.update({k: "email_connection" for k in ("incoming", "spam", "sent", "drafts")})
    for source, field in required.items():
        if state["daily_review"][field]:
            coverage = evidence.get("coverage", {}).get(source, {})
            require(coverage.get("checked") is True and not coverage.get("may_be_truncated"), f"Preview did not verify {source}")
    return {"configuration_id": state["configuration_id"], "execution_id": evidence["execution_id"]}


def checked_path(path):
    absolute = Path(os.path.abspath(Path(path).expanduser()))
    for part in (absolute, *absolute.parents):
        require(not part.is_symlink(), "Linked settings paths are not supported")
        if part.exists():
            require(not getattr(part.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0), "Reparse settings paths are not supported")
    return absolute


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SettingsError("Settings are being edited; retry after the current operation") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def read_state(path, catalogue):
    if not path.exists():
        return fresh()
    return validate(json.loads(path.read_text(encoding="utf-8")), catalogue)


def save_state(path, state):
    fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dispatch(home, catalogue, command):
    path = checked_path(checked_path(home) / "hermes-agent-skills" / "user-settings.json")
    action = command.get("action")
    if action in ("get_settings", "resolve_route", "plan_daily_review", "plan_bindings", "plan_calendar_binding"):
        state = read_state(path, catalogue)
        if action == "get_settings":
            return status(state)
        if action == "resolve_route":
            return resolve_route(state, catalogue, command["route_key"], command["workflow"])
        if action == "plan_bindings":
            return binding_plan(state, catalogue, command["route_key"], command["workflow"], command["edits"])
        if action == "plan_calendar_binding":
            return calendar_binding_plan(state, command["workflow"])
        return daily_plan(state, command["workflow"], command.get("mode", "preview"), command.get("calendar_workflow"))
    require(action in ("update_settings", "record_preview", "record_deployment"), "Unknown settings action")
    require(identifier(command.get("request_id")), "A stable request ID is required")
    fingerprint = hashlib.sha256(json.dumps(command, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with locked(path):
        state = read_state(path, catalogue)
        prior = state.get("last_command") or {}
        if prior.get("request_id") == command["request_id"]:
            require(prior["fingerprint"] == fingerprint, "Request ID reused with changed arguments")
            return status(state)
        require(type(command.get("expected_revision")) is int and command["expected_revision"] == state["revision"], "Settings changed; reload before editing")
        if action == "update_settings":
            state = update(state, command["changes"], catalogue)
        elif action == "record_preview":
            state["preview"] = accept_preview(state, command["evidence"])
        else:
            state["deployment"] = verify_applied(state, command["workflow"], command["mode"], command.get("calendar_workflow"))
        state["revision"] += 1
        state["last_command"] = {"request_id": command["request_id"], "fingerprint": fingerprint}
        save_state(path, state)
        return status(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", required=True)
    parser.add_argument("--catalogue", type=Path, default=Path(__file__).with_name("capabilities.json"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.read(4_000_001)
        require(len(raw) <= 4_000_000, "Settings command is too large")
        result = dispatch(args.hermes_home, json.loads(args.catalogue.read_text(encoding="utf-8-sig")), json.loads(raw))
        print(json.dumps(result))
        return 0
    except (SettingsError, KeyError, TypeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc), "remote_changed": False}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
