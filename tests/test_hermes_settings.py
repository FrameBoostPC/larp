"""Profile setup acceptance, using fictional accounts and workflow exports."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hermes_settings", ROOT / "components/hermes-orchestration/settings.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CATALOGUE = json.loads((ROOT / "components/hermes-orchestration/capabilities.json").read_text())


def route(workflow_id):
    return {"workflow_id": workflow_id, "trigger": "Agent request", "terminal_nodes": ["Return result"]}


def configured():
    return s.update(s.fresh(), {
        "instance_url": "https://n8n.example.com",
        "routes": {"priorities": route("daily"), "calendar": route("calendar")},
        "connections": {"mail": {"provider": "gmail", "credential_type": "gmailOAuth2", "credential_id": "gmail-new", "credential_name": "Selected mail", "account_id": "buyer@example.com"},
                        "notion": {"provider": "notion", "credential_type": "notionApi", "credential_id": "notion-new", "credential_name": "Selected workspace", "account_id": "workspace-new"}},
        "resources": {"work": {"kind": "n8n_table", "resource_id": "table-new", "label": "My work"},
                      "calendar": {"kind": "notion_data_source", "resource_id": "calendar-new", "label": "My schedule", "connection_key": "notion"}},
        "daily_review": {"time": "07:30", "timezone": "Australia/Brisbane", "storage_resource": "work", "workbench_resource": "work", "email_connection": "mail"},
    }, CATALOGUE)


def daily_workflow():
    names = ["Review configuration", "Daily preparation time", "Read last complete snapshot", "Read latest prepared snapshot", "Save daily review snapshot", "Read pending work", "Read pending email review", "Read organisation receipts", "Read incoming email", "Check recent spam", "Read recent sent context", "Read existing reply drafts", "Read connected calendar"]
    return {"id": "daily", "versionId": "version-1", "active": False, "settings": {}, "nodes": [
        {"name": n, "type": "fixture", "parameters": {"preserved": True}, "credentials": {"gmailOAuth2": {"id": "gmail-old"}}} for n in names
    ] + [{"name": "Agent request", "type": "@n8n/n8n-nodes-langchain.chatTrigger", "parameters": {"public": False}}, {"name": "Return result", "type": "code", "parameters": {}}]}


def calendar_workflow():
    return {"id": "calendar", "versionId": "calendar-v1", "activeVersionId": "calendar-v1", "active": True, "activeVersion": {"sameAsDraft": True}, "nodes": [
        {"name": "Scheduling settings", "type": "n8n-nodes-base.code", "parameters": {"jsCode": 'return [{json:{settings:{data_source_id:"calendar-new",max_records:500}}}];'}},
        {"name": "Parse", "type": "n8n-nodes-base.code", "parameters": {"jsCode": 'const actions=["daily_review_context"];'}},
        *[{"name": n, "type": "n8n-nodes-base.notion", "parameters": {"dataSourceId": {"value": '={{ $("Scheduling settings").first().json.settings.data_source_id }}'}, "simple": False}, "credentials": {"notionApi": {"id": "notion-new"}}} for n in ("Read Notion schedule", "Read Notion schedule schema", "Create item")]]}


def apply(w, plan):
    w = copy.deepcopy(w)
    for op in plan["operations"]:
        if op["type"] == "setWorkflowSettings":
            w["settings"].update(op["settings"])
            continue
        node = s.workflow_node(w, op["nodeName"])
        if op["type"] == "updateNodeParameters":
            node["parameters"] = op["parameters"]
        elif op["type"] == "setNodeDisabled":
            node["disabled"] = op["disabled"]
        elif op["type"] == "setNodeCredential":
            node["credentials"][op["credentialKey"]] = {"id": op["credentialId"], "name": op["credentialName"]}
    return w


def evidence(state):
    return {"workflow_id": "daily", "configuration_id": state["configuration_id"], "execution_id": "preview-1", "collection_status": "complete", "provider_reads": "live", "coverage": {k: {"checked": True, "may_be_truncated": False} for k in ("work", "incoming", "spam", "sent", "drafts", "calendar")}}


class SettingsTests(unittest.TestCase):
    def test_actual_package_installs_a_runnable_helper_and_preserves_choices(self):
        installer_spec = importlib.util.spec_from_file_location("setup_installer", ROOT / "scripts/install_hermes.py")
        installer = importlib.util.module_from_spec(installer_spec)
        installer_spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "profile"
            installer.apply_plan(installer.build_plan(ROOT, home))
            helper = home / "hermes-agent-skills/settings.py"
            command = {"action": "update_settings", "request_id": "installed-setup", "expected_revision": 0, "changes": {"daily_review": {"time": "08:15"}}}
            result = subprocess.run([sys.executable, str(helper), "--hermes-home", str(home)], input=json.dumps(command), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            saved = json.loads(result.stdout)
            self.assertEqual(saved["status"], "setup_required")
            self.assertEqual(saved["settings"]["daily_review"]["time"], "08:15")
            user_file = home / "hermes-agent-skills/user-settings.json"
            before = user_file.read_bytes()
            installer.apply_plan(installer.build_plan(ROOT, home))
            self.assertEqual(user_file.read_bytes(), before)

    def test_fresh_read_is_deferred_without_inherited_accounts_or_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = s.dispatch(directory, CATALOGUE, {"action": "get_settings"})
            self.assertEqual(out["status"], "setup_required")
            self.assertEqual(out["settings"]["routes"], {})
            self.assertFalse(list(Path(directory).iterdir()))

    def test_partial_setup_resume_retry_and_revision_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            cmd = {"action": "update_settings", "request_id": "one", "expected_revision": 0, "changes": {"daily_review": {"time": "07:30"}}}
            first = s.dispatch(directory, CATALOGUE, cmd)
            self.assertEqual(first["status"], "setup_required")
            self.assertEqual(s.dispatch(directory, CATALOGUE, cmd), first)
            with self.assertRaisesRegex(s.SettingsError, "reused"):
                s.dispatch(directory, CATALOGUE, {**cmd, "changes": {}})
            with self.assertRaisesRegex(s.SettingsError, "reload"):
                s.dispatch(directory, CATALOGUE, {**cmd, "request_id": "two"})
            result = s.dispatch(directory, CATALOGUE, {**cmd, "request_id": "two", "expected_revision": 1, "changes": {"daily_review": {"timezone": "Australia/Brisbane"}}})
            self.assertEqual(result["settings"]["daily_review"]["time"], "07:30")
            self.assertEqual(result["settings"]["revision"], 2)
            self.assertFalse(result["remote_changed"])

    def test_invalid_or_secret_metadata_is_rejected(self):
        state = configured()
        patches = [
            {"connections": {"mail": {**state["connections"]["mail"], "token": "secret"}}},
            {"connections": {"mail": {**state["connections"]["mail"], "provider": "outlook"}}},
            {"daily_review": {"time": "24:00"}}, {"daily_review": {"timezone": "Unknown/Place"}},
            {"daily_review": {"calendar_resource": "absent"}},
            {"routes": {"retired-repurposing": route("old")}},
            {"instance_url": "https://user:password@example.com"},
        ]
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(s.SettingsError):
                s.update(state, patch, CATALOGUE)

    def test_each_binding_edit_invalidates_preview_and_retains_previous_receipt(self):
        state = configured()
        state["preview"] = s.accept_preview(state, evidence(state))
        state["deployment"] = {"configuration_id": state["configuration_id"], "active": True}
        for patch in ({"daily_review": {"time": "08:00"}}, {"routes": {"priorities": route("new-daily")}}, {"resources": {"work": {"kind": "n8n_table", "resource_id": "another", "label": "Other work"}}}, {"connections": {"mail": {**state["connections"]["mail"], "credential_id": "other-account"}}}):
            result = s.update(state, patch, CATALOGUE)
            self.assertNotEqual(result["configuration_id"], state["configuration_id"])
            self.assertIsNone(result["preview"])
            self.assertEqual(result["previous_routes"], state["routes"])
            self.assertEqual(result["deployment"], state["deployment"])
            self.assertEqual(s.status(result)["status"], "ready_to_preview")

    def test_plan_rebinds_every_reader_and_storage_without_mutating_input(self):
        state, w = configured(), daily_workflow()
        plan = s.daily_plan(state, w)
        self.assertEqual(plan["expected_version_id"], "version-1")
        self.assertFalse(plan["publish"])
        changed = apply(w, plan)
        self.assertTrue(s.workflow_node(changed, "Daily preparation time")["disabled"])
        for n in ("Read incoming email", "Check recent spam", "Read recent sent context", "Read existing reply drafts"):
            self.assertEqual(s.workflow_node(changed, n)["credentials"]["gmailOAuth2"]["id"], "gmail-new")
            self.assertEqual(s.workflow_node(w, n)["credentials"]["gmailOAuth2"]["id"], "gmail-old")
        for n in ("Read last complete snapshot", "Read latest prepared snapshot", "Save daily review snapshot", "Read pending work"):
            self.assertEqual(s.workflow_node(changed, n)["parameters"]["dataTableId"]["value"], "table-new")
            self.assertTrue(s.workflow_node(changed, n)["parameters"]["preserved"])
        self.assertEqual(s.verify_applied(state, changed, "preview")["mode"], "preview")

    def test_activation_requires_live_current_complete_preview_and_published_readback(self):
        state, w = configured(), daily_workflow()
        with self.assertRaisesRegex(s.SettingsError, "preview"):
            s.daily_plan(state, w, "active")
        for patch in ({"provider_reads": "pinned"}, {"configuration_id": "old"}, {"collection_status": "partial"}, {"coverage": {}}):
            with self.subTest(patch=patch), self.assertRaises(s.SettingsError):
                s.accept_preview(state, {**evidence(state), **patch})
        state["preview"] = s.accept_preview(state, evidence(state))
        changed = apply(w, s.daily_plan(state, w, "active"))
        with self.assertRaisesRegex(s.SettingsError, "published"):
            s.verify_applied(state, changed, "active")
        changed.update(active=True, activeVersionId="version-1")
        self.assertTrue(s.verify_applied(state, changed, "active")["active"])
        s.workflow_node(changed, "Read incoming email")["credentials"]["gmailOAuth2"]["id"] = "wrong"
        with self.assertRaisesRegex(s.SettingsError, "credential"):
            s.verify_applied(state, changed, "active")

    def test_wrong_storage_cannot_be_recorded_as_applied(self):
        state, w = configured(), daily_workflow()
        changed = apply(w, s.daily_plan(state, w))
        s.workflow_node(changed, "Save daily review snapshot")["parameters"]["dataTableId"]["value"] = "old"
        with self.assertRaisesRegex(s.SettingsError, "Binding"):
            s.verify_applied(state, changed, "preview")

    def test_work_only_and_disconnect_do_not_require_mail_or_calendar(self):
        state = s.update(configured(), {"daily_review": {"email_connection": None}}, CATALOGUE)
        plan = s.daily_plan(state, daily_workflow())
        self.assertFalse(any(op["type"] == "setNodeCredential" for op in plan["operations"]))
        self.assertFalse(s.runtime_configuration(state, "preview")["sources"]["email"])
        state = s.update(state, {"daily_review": {"workbench_resource": None, "time": None}}, CATALOGUE)
        for mode in ("paused", "setup_required"):
            plan = s.daily_plan(state, daily_workflow(), mode)
            self.assertEqual(len(plan["operations"]), 2)
            self.assertTrue(plan["operations"][1]["disabled"])

    def test_calendar_binding_updates_shared_owner_and_verifies_published_resource(self):
        state = s.update(configured(), {"daily_review": {"calendar_resource": "calendar"}}, CATALOGUE)
        calendar = calendar_workflow()
        plan = s.daily_plan(state, daily_workflow(), calendar_export=calendar)
        self.assertEqual(next(op for op in plan["operations"] if op.get("nodeName") == "Read connected calendar")["parameters"]["workflowId"]["value"], "calendar")
        calendar["nodes"][0]["parameters"]["jsCode"] = calendar["nodes"][0]["parameters"]["jsCode"].replace("calendar-new", "calendar-old")
        with self.assertRaisesRegex(s.SettingsError, "different resource"):
            s.daily_plan(state, daily_workflow(), calendar_export=calendar)
        binding = s.calendar_binding_plan(state, calendar)
        self.assertEqual(binding["previous_resource_id"], "calendar-old")
        self.assertEqual(len(binding["operations"]), 4)
        rebound = apply(calendar, binding)
        self.assertEqual(s.calendar_source(rebound), "calendar-new")
        self.assertIn("max_records:500", rebound["nodes"][0]["parameters"]["jsCode"])
        rebound["nodes"][2]["credentials"]["notionApi"]["id"] = "other"
        with self.assertRaisesRegex(s.SettingsError, "different account"):
            s.daily_plan(state, daily_workflow(), calendar_export=rebound)

    def test_generic_binding_changes_only_explicit_owned_parameters(self):
        state, w = configured(), daily_workflow()
        s.workflow_node(w, "Read pending work")["parameters"]["dataTableId"] = {"__rl": True, "mode": "list", "value": "old"}
        plan = s.binding_plan(state, CATALOGUE, "priorities", w, [{"node": "Read pending work", "resource_key": "work", "parameter_path": ["dataTableId"]}])
        self.assertEqual(plan["operations"][0]["parameters"]["dataTableId"]["value"], "table-new")
        self.assertTrue(plan["operations"][0]["parameters"]["preserved"])
        with self.assertRaisesRegex(s.SettingsError, "Only linked-resource"):
            s.binding_plan(state, CATALOGUE, "priorities", w, [{"node": "Read pending work", "resource_key": "work", "parameter_path": ["jsCode"]}])

    def test_dispatch_respects_current_profile_private_trigger_and_publication(self):
        state, w = configured(), daily_workflow()
        state["preview"] = s.accept_preview(state, evidence(state))
        w = apply(w, s.daily_plan(state, w, "active"))
        w.update(active=True, activeVersionId="version-1", activeVersion={"sameAsDraft": True}, canExecute=True)
        self.assertEqual(s.resolve_route(state, CATALOGUE, "priorities", w)["workflow_id"], "daily")
        for key, value in (("active", False), ("canExecute", False)):
            with self.assertRaises(s.SettingsError):
                s.resolve_route(state, CATALOGUE, "priorities", {**w, key: value})
        s.workflow_node(w, "Agent request")["parameters"]["public"] = True
        with self.assertRaisesRegex(s.SettingsError, "private"):
            s.resolve_route(state, CATALOGUE, "priorities", w)
        with self.assertRaisesRegex(s.SettingsError, "Internal/retired"):
            s.resolve_route(state, CATALOGUE, "prospect-worker", w)


if __name__ == "__main__":
    unittest.main()
