"""Exercise the real file-input boundary without connected accounts."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "components" / "planning-sync"))
import cli


class PlanningSyncCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = self.path / "config.json"
        self.config.write_text(json.dumps({"state_path": "state.sqlite3", "notion": None, "calendar": None}))
        self.plan = ROOT / "skills" / "project-planner" / "examples" / "example-output.json"

    def run_cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            result = cli.main(["--config", str(self.config), *args])
        self.assertEqual(result, 0)
        return json.loads(output.getvalue())

    def imported(self):
        return self.run_cli("import-plan", "--project-id", "project-a", "--request-id", "import-a", "--input", str(self.plan))

    def write_proposal(self, task, project_id="project-a"):
        proposal = json.loads((ROOT / "skills" / "calendar-planner" / "examples" / "example-output.json").read_text())
        proposal["data"]["project_id"] = project_id
        proposal["data"]["operations"] = [{"task_id": task["id"], "expected_revision": task["revision"], "action": "update_task", "patch": {"title": "Updated through CLI"}, "reason": "User renamed task"}]
        path = self.path / "proposal.json"
        path.write_text(json.dumps(proposal))
        return str(path)

    def test_import_replay_then_apply_and_status_use_same_persisted_task(self):
        first = self.imported()
        self.assertEqual(first, self.imported())
        result = self.run_cli("apply", "--request-id", "rename", "--input", self.write_proposal(first[0]))
        self.assertEqual(result[0]["id"], first[0]["id"])
        status = self.run_cli("status")
        self.assertEqual(len(status["tasks"]), len(first))
        self.assertEqual(status["tasks"][0]["title"], "Updated through CLI")
        self.assertEqual(status["configured_surfaces"], [])

    def test_wrong_project_proposal_cannot_mutate_saved_task(self):
        task = self.imported()[0]
        path = self.write_proposal(task, "unrelated-project")
        with self.assertRaisesRegex(ValueError, "different project"):
            self.run_cli("apply", "--request-id", "wrong-project", "--input", path)
        self.assertEqual(self.run_cli("status")["tasks"][0], task)

    def test_schema_invalid_patch_is_rejected_before_application(self):
        task = self.imported()[0]
        path = Path(self.write_proposal(task))
        payload = json.loads(path.read_text())
        payload["data"]["operations"][0]["patch"] = {"project_id": "other"}
        path.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            self.run_cli("apply", "--request-id", "invalid", "--input", str(path))
        self.assertEqual(self.run_cli("status")["tasks"][0], task)

    def test_unconfigured_sync_cannot_report_success(self):
        with self.assertRaisesRegex(ValueError, "No external adapters configured"):
            self.run_cli("sync")


if __name__ == "__main__":
    unittest.main()
