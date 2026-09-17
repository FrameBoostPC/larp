"""Joining an existing review owner must never provision or activate it."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shared_settings", ROOT / "components/hermes-orchestration/settings.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CATALOGUE = json.loads((ROOT / "components/hermes-orchestration/capabilities.json").read_text())


def choices():
    return {"instance_url": "https://automation.example.com", "routes": {
        "priorities": {"workflow_id": "shared-daily", "trigger": "Agent request", "terminal_nodes": ["Return result"]}}}


def owner():
    return {"id": "shared-daily", "active": True, "canExecute": True, "versionId": "v1",
            "activeVersionId": "v1", "activeVersion": {"sameAsDraft": True}, "nodes": [
                {"name": "Agent request", "type": "n8n.chatTrigger", "parameters": {"public": False}},
                {"name": "Return result", "type": "n8n.code", "parameters": {}},
                {"name": "Review configuration", "type": "n8n.set", "parameters": {"jsonOutput": json.dumps({"review_config": {
                    "configuration_id": "owner-configuration", "mode": "paused", "schedule_preference": None,
                    "labels": {"email": "private-fixture@example.com"}, "sources": {"email": True}}})}}]}


class SharedSetupTests(unittest.TestCase):
    def test_setup_only_read_is_possible_before_source_selection(self):
        state = s.update(s.fresh(), choices(), CATALOGUE)
        result = s.resolve_route(state, CATALOGUE, "priorities", owner(), "get_setup")
        self.assertEqual(["get_setup"], result["actions"])
        self.assertEqual("owner-configuration", result["configuration_id"])
        with self.assertRaisesRegex(s.SettingsError, "Apply and verify"):
            s.resolve_route(state, CATALOGUE, "priorities", owner(), "get_daily_review")

    def test_shared_connection_is_local_idempotent_and_can_read_saved_review(self):
        with tempfile.TemporaryDirectory() as home:
            s.dispatch(home, CATALOGUE, {"action": "update_settings", "request_id": "select-routes",
                       "expected_revision": 0, "changes": choices()})
            workflow = owner()
            before = copy.deepcopy(workflow)
            command = {"action": "connect_shared_daily_review", "request_id": "join-owner",
                       "expected_revision": 1, "workflow": workflow}
            result = s.dispatch(home, CATALOGUE, command)
            self.assertEqual(result, s.dispatch(home, CATALOGUE, command))
            self.assertEqual("shared_configured", result["status"])
            self.assertFalse(result["remote_changed"])
            self.assertEqual(before, workflow)
            self.assertEqual({}, result["settings"]["connections"])
            self.assertIsNone(result["settings"]["daily_review"]["time"])
            self.assertIsNone(result["settings"]["deployment"])
            saved = (Path(home) / "hermes-agent-skills/user-settings.json").read_text()
            self.assertNotIn("private-fixture", saved)
            response = s.dispatch(home, CATALOGUE, {"action": "resolve_route", "route_key": "priorities", "workflow": workflow})
            self.assertIn("get_daily_review", response["actions"])
            self.assertEqual("owner-configuration", response["configuration_id"])
            with self.assertRaisesRegex(s.SettingsError, "select your own settings"):
                s.daily_plan(result["settings"], workflow, "paused")

    def test_current_publication_and_execution_access_are_required(self):
        state = s.update(s.fresh(), choices(), CATALOGUE)
        for key, value in (("active", False), ("canExecute", False), ("id", "other-owner"), ("isArchived", True)):
            with self.subTest(key=key), self.assertRaises(s.SettingsError):
                s.connect_shared_review(state, CATALOGUE, {**owner(), key: value})
        for changed in ("public", "disabled"):
            w = owner()
            trigger = w["nodes"][0]
            (trigger["parameters"] if changed == "public" else trigger)[changed] = True
            with self.assertRaises(s.SettingsError):
                s.connect_shared_review(state, CATALOGUE, w)

    def test_changed_remote_configuration_blocks_until_reselected(self):
        state = s.update(s.fresh(), choices(), CATALOGUE)
        state["shared_daily_review"] = s.connect_shared_review(state, CATALOGUE, owner())
        for field, value in (("mode", "setup_required"), ("configuration_id", "different-owner"), ("sources", {"calendar": True})):
            w = owner()
            node = w["nodes"][2]
            config = json.loads(node["parameters"]["jsonOutput"])
            config["review_config"][field] = value
            node["parameters"]["jsonOutput"] = json.dumps(config)
            with self.subTest(field=field), self.assertRaisesRegex(s.SettingsError, "Shared review configuration changed"):
                s.resolve_route(state, CATALOGUE, "priorities", w)
            self.assertEqual(["get_setup"], s.resolve_route(state, CATALOGUE, "priorities", w, "get_setup")["actions"])

    def test_draft_cannot_supply_a_different_shared_configuration(self):
        w = owner()
        w["activeVersion"] = {"nodes": copy.deepcopy(w["nodes"])}
        w["versionId"] = "unpublished-draft"
        w["nodes"][2]["parameters"]["jsonOutput"] = '{"review_config":{"configuration_id":"wrong","mode":"active"}}'
        state = s.update(s.fresh(), choices(), CATALOGUE)
        receipt = s.connect_shared_review(state, CATALOGUE, w)
        self.assertEqual("owner-configuration", receipt["configuration_id"])

    def test_local_selection_changes_invalidate_shared_receipt_and_old_profiles_load(self):
        state = s.update(s.fresh(), choices(), CATALOGUE)
        state["shared_daily_review"] = s.connect_shared_review(state, CATALOGUE, owner())
        for change in ({"instance_url": "https://different.example.com"}, {"routes": {"priorities": None}}, {"daily_review": {"time": "07:30"}}):
            modified = s.update(state, change, CATALOGUE)
            self.assertIsNone(modified["shared_daily_review"])
            self.assertNotEqual("shared_configured", s.status(modified)["status"])
        old = s.fresh()
        old.pop("shared_daily_review")
        self.assertEqual("setup_required", s.status(s.validate(old, CATALOGUE))["status"])

    def test_stale_join_command_and_unconfigured_owner_do_not_save_receipt(self):
        with tempfile.TemporaryDirectory() as home:
            s.dispatch(home, CATALOGUE, {"action": "update_settings", "request_id": "routes", "expected_revision": 0, "changes": choices()})
            command = {"action": "connect_shared_daily_review", "request_id": "join", "expected_revision": 0, "workflow": owner()}
            with self.assertRaisesRegex(s.SettingsError, "reload"):
                s.dispatch(home, CATALOGUE, command)
            command["expected_revision"] = 1
            command["workflow"]["nodes"][2]["parameters"]["jsonOutput"] = '{"review_config":{"configuration_id":"fresh","mode":"setup_required"}}'
            with self.assertRaisesRegex(s.SettingsError, "already be configured"):
                s.dispatch(home, CATALOGUE, command)
            self.assertIsNone(s.dispatch(home, CATALOGUE, {"action": "get_settings"})["settings"]["shared_daily_review"])


if __name__ == "__main__":
    unittest.main()
