"""Optional n8n connection setup, using fictional local profiles only."""
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_n8n_under_test", ROOT / "scripts/install_hermes.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
URL = "https://automation.example.com/mcp-server/http"


class N8nConfigTests(unittest.TestCase):
    def merge(self, raw, name="n8n_larp"):
        return installer.n8n_config(raw, URL, name)

    def test_add_preserves_model_comments_secrets_and_other_servers_verbatim(self):
        raw = (b"# Personal settings\r\nmodel: chosen-model\r\nmcp_servers:\r\n"
               b"  # Keep this provider\r\n  existing:\r\n    url: https://other.example.com\r\n"
               b"    headers: {Authorization: 'Bearer local-fixture'}\r\nvoice: {enabled: true}\r\n")
        merged, name = self.merge(raw)
        data = yaml.safe_load(merged)
        self.assertEqual(name, "n8n_larp")
        old = yaml.safe_load(raw)
        new = data["mcp_servers"].pop(name)
        self.assertEqual(old, data)
        self.assertEqual(URL, new["url"])
        self.assertEqual("oauth", new["auth"])
        self.assertEqual(list(installer.N8N_TOOLS), new["tools"]["include"])
        self.assertIn(b"  existing:\r\n    url: https://other.example.com\r\n    headers: {Authorization: 'Bearer local-fixture'}", merged)
        self.assertNotIn(b"\n", merged.replace(b"\r\n", b""))

    def test_absent_empty_and_null_servers_with_bom_and_comments(self):
        for raw in (b"model: local\n", b"model: local", b"model: local\nmcp_servers: {}\n",
                    b"mcp_servers: null # leave comment\nmodel: local\n",
                    b"mcp_servers:\nmodel: local\n", b"\xef\xbb\xbfmodel: local\n"):
            with self.subTest(raw=raw):
                merged, _ = self.merge(raw)
                self.assertEqual(URL, yaml.safe_load(merged)["mcp_servers"]["n8n_larp"]["url"])
                self.assertEqual(merged, self.merge(merged)[0])
                self.assertEqual(raw.startswith(b"\xef\xbb\xbf"), merged.startswith(b"\xef\xbb\xbf"))

    def test_existing_connection_is_reused_without_changing_auth_or_filters(self):
        raw = ("model: local\nmcp_servers:\n  existing_n8n:\n    url: " + URL + "/\n"
               "    headers: {Authorization: 'Bearer local-fixture'}\n"
               "    tools: {include: [get_workflow_details]}\n").encode()
        merged, name = self.merge(raw)
        self.assertEqual(raw, merged)
        self.assertEqual("existing_n8n", name)

    def test_duplicate_endpoints_require_named_choice(self):
        raw = yaml.safe_dump({"model": "local", "mcp_servers": {n: {"url": URL} for n in ("one", "two")}}).encode()
        with self.assertRaisesRegex(installer.InstallError, "Several connections"):
            self.merge(raw)
        self.assertEqual((raw, "two"), self.merge(raw, "two"))

    def test_conflicts_never_replace_existing_configuration(self):
        invalid = (
            b"model: local\nmcp_servers: {n8n_larp: {url: https://another.example.com}}\n",
            f"mcp_servers:\n  disabled:\n    url: {URL}\n    enabled: false\n".encode(),
            f"mcp_servers:\n  mixed:\n    url: {URL}\n    command: secret-command\n".encode(),
            b"model: first\nmodel: second\n",
            b"mcp_servers: {}\nmcp_servers: {}\n",
            b"mcp_servers: [invalid]\n",
            b"model: local\n---\nmodel: another\n",
            b"model: local\n...\n",
            b"{model: local}\n",
            b"model: !!python/object:example {}\n",
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(installer.InstallError):
                self.merge(raw)

    def test_yaml_alias_cannot_modify_another_config_section(self):
        raw = b"other: &shared\n  old: {url: https://example.com}\nmcp_servers: *shared\n"
        with self.assertRaises(installer.InstallError):
            self.merge(raw)

    def test_parse_error_does_not_print_config_or_secret_line(self):
        secret = "local-private-fixture"
        with self.assertRaises(installer.InstallError) as caught:
            self.merge(f"broken: [\n  secret: {secret}\n".encode())
        self.assertNotIn(secret, str(caught.exception))

    def test_endpoints_and_names_are_validated(self):
        for url in ("http://automation.example.com/mcp-server/http", "https://user:pass@example.com/mcp-server/http",
                    URL + "?token=private", URL + "#fragment", "https://example.com/webhook/run", "https://bad host/mcp-server/http",
                    "https://[invalid/mcp-server/http", "https://example.com:invalid/mcp-server/http"):
            with self.subTest(url=url), self.assertRaises(installer.InstallError):
                installer.n8n_config(b"model: local\n", url, "n8n_larp")
        for name in ("../outside", "bad name", "n8n;command", ""):
            with self.subTest(name=name), self.assertRaises(installer.InstallError):
                self.merge(b"model: local\n", name)


class N8nInstallationTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.home = Path(area.name) / "active-profile"
        self.home.mkdir()
        self.config = self.home / "config.yaml"
        self.original = b"# Keep my settings\nmodel: local-fixture\n"
        self.config.write_bytes(self.original)

    def plan(self):
        plan = installer.build_plan(ROOT, self.home)
        installer.add_n8n_to_plan(plan, URL, "n8n_larp")
        return plan

    def test_preview_apply_backup_check_and_user_owned_config(self):
        plan = self.plan()
        self.assertEqual(self.original, self.config.read_bytes())
        self.assertFalse((self.home / "skills").exists())
        backup = installer.apply_plan(plan)
        self.assertEqual(self.original, (backup / "config.yaml").read_bytes())
        state = json.loads((self.home / installer.STATE_PATH).read_text())
        self.assertNotIn("config.yaml", state["files"])
        self.assertEqual({}, self.plan()["changes"])
        changed = self.config.read_bytes() + b"voice: {enabled: true}\n"
        self.config.write_bytes(changed)
        installer.apply_plan(self.plan())
        self.assertEqual(changed, self.config.read_bytes())
        self.assertEqual({}, installer.build_plan(ROOT, self.home)["changes"])

    def test_missing_profile_or_name_conflict_blocks_whole_install(self):
        self.config.unlink()
        with self.assertRaisesRegex(installer.InstallError, "existing active Hermes profile"):
            self.plan()
        self.assertFalse((self.home / "skills").exists())
        self.config.write_bytes(b"mcp_servers: {n8n_larp: {url: https://another.example.com}}\n")
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertFalse((self.home / "SOUL.md").exists())

    def test_concurrent_config_edit_blocks_before_any_install_writes(self):
        plan = self.plan()
        changed = self.original + b"voice: {enabled: true}\n"
        self.config.write_bytes(changed)
        with self.assertRaisesRegex(installer.InstallError, "Changed since preflight"):
            installer.apply_plan(plan)
        self.assertEqual(changed, self.config.read_bytes())
        self.assertFalse((self.home / "SOUL.md").exists())

    def test_cli_reports_configuration_separately_from_authentication(self):
        args = ["--hermes-home", str(self.home), "--n8n-url", URL]
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(0, installer.main(args))
            self.assertEqual(self.original, self.config.read_bytes())
            self.assertEqual(1, installer.main(args + ["--check"]))
            self.assertEqual(0, installer.main(args + ["--apply"]))
            self.assertEqual(0, installer.main(args + ["--check"]))
        self.assertIn("authentication and workflow access are NOT verified", output.getvalue())
        self.assertIn("hermes mcp login n8n_larp", output.getvalue())


if __name__ == "__main__":
    unittest.main()
