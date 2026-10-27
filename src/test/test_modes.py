"""Tests for the mode launcher and the SessionStart hook."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src" / "plugin" / "worktools" / "scripts" / "mode"))
sys.path.insert(0, str(REPO / "src" / "launcher"))

import modes as mode_lib  # noqa: E402
import worktools  # noqa: E402
import session_start  # noqa: E402

LAUNCHER = REPO / "src" / "launcher" / "worktools.py"


def run(*args, stdin=""):
    return subprocess.run([sys.executable, str(LAUNCHER), *args], input=stdin,
                          capture_output=True, text=True)


class ModeTests(unittest.TestCase):
    def test_names_and_aliases(self):
        for name, mode in [("eco", "eco"), ("C", "eco"), ("haiku", "eco"), ("balanced", "balanced"),
                           ("b", "balanced"), ("sonnet-haiku", "balanced"), ("x", None)]:
            self.assertEqual(mode_lib.resolve(name), mode, name)

    def test_settings(self):
        eco = mode_lib.settings_for("eco")
        self.assertEqual(eco["model"], "haiku")
        self.assertEqual(eco["env"]["CLAUDE_CODE_SUBAGENT_MODEL_FORCE"], "1")
        self.assertEqual(eco["env"]["CODE_SURVEY_MODE"], "eco")
        bal = mode_lib.settings_for("balanced")
        self.assertEqual((bal["model"], bal["env"]["CLAUDE_CODE_SUBAGENT_MODEL"]), ("sonnet", "haiku"))


class LauncherTests(unittest.TestCase):
    def test_dry_run_passes_the_rest_to_claude(self):
        proc = run("--dry-run", "balanced", "-p", "survey this")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        command = json.loads(proc.stdout)
        self.assertEqual(command[:3], ["claude", "--model", "sonnet"])
        self.assertEqual(json.loads(command[4])["env"]["CODE_SURVEY_MODE"], "balanced")
        self.assertEqual(command[5:], ["-p", "survey this"])

    def test_unknown_mode_is_an_error(self):
        proc = run("--dry-run", "ecco")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown mode", proc.stderr)

    def test_no_mode_without_terminal_is_refused(self):
        for args in ([], ["-p", "survey"], ["survey this repo"]):
            proc = run("--dry-run", *args)
            self.assertEqual(proc.returncode, 2, args)
            self.assertIn("no mode given", proc.stderr)

    def test_ask_by_number_name_retry_and_cancel(self):
        modes = mode_lib.load()
        out = io.StringIO()
        self.assertEqual(worktools.ask(modes, io.StringIO("1\n"), out), "eco")
        self.assertEqual(worktools.ask(modes, io.StringIO("b\n"), out), "balanced")
        self.assertEqual(worktools.ask(modes, io.StringIO("9\nbalanced\n"), out), "balanced")
        self.assertIsNone(worktools.ask(modes, io.StringIO("q\n"), out))
        self.assertIsNone(worktools.ask(modes, io.StringIO(""), out))
        self.assertIn("1) eco", out.getvalue())


class SessionStartTests(unittest.TestCase):
    def test_with_mode(self):
        text = session_start.context({"CODE_SURVEY_MODE": "eco"})
        self.assertIn("worktools mode: eco", text)

    def test_without_mode_lists_commands(self):
        text = session_start.context({})
        self.assertIn("no mode was chosen", text)
        self.assertIn("`worktools eco`", text)
        self.assertIn("`worktools balanced`", text)


class PromptGuardTests(unittest.TestCase):
    def setUp(self):
        import prompt_guard
        self.guard = prompt_guard
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mode_set_passes(self):
        self.assertIsNone(self.guard.decide({"session_id": "s"}, {"CODE_SURVEY_MODE": "eco"}, self.state))

    def test_non_interactive_always_blocks(self):
        env = {"CLAUDE_CODE_ENTRYPOINT": "sdk-cli", "CLAUDE_CODE_SESSION_ATTENDED": "0"}
        for _ in range(2):
            out = self.guard.decide({"session_id": "s"}, env, self.state)
            self.assertEqual(out["decision"], "block")
            self.assertIn("worktools balanced", out["reason"])

    def test_interactive_blocks_once(self):
        env = {"CLAUDE_CODE_ENTRYPOINT": "cli"}
        first = self.guard.decide({"session_id": "s"}, env, self.state)
        self.assertEqual(first["decision"], "block")
        self.assertIn("worktools eco", first["reason"])
        self.assertIsNone(self.guard.decide({"session_id": "s"}, env, self.state))
        self.assertEqual(self.guard.decide({"session_id": "t"}, env, self.state)["decision"], "block")

    def test_hook_output_shape(self):
        script = REPO / "src" / "plugin" / "worktools" / "scripts" / "mode" / "session_start.py"
        env = {k: v for k, v in os.environ.items() if k != "CODE_SURVEY_MODE"}
        proc = subprocess.run([sys.executable, str(script)], input="{}", capture_output=True,
                              text=True, env=env)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        self.assertIn("no mode was chosen", out["additionalContext"])


class InstallLauncherTests(unittest.TestCase):
    def test_link_and_unlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            target = Path(tmp) / "settings.json"
            base = [sys.executable, str(REPO / "src" / "setup" / "install.py"), "--target", str(target),
                    "--no-statusline", "--launcher", "--bin-dir", str(bin_dir)]
            subprocess.run(base, capture_output=True, text=True, check=True)
            link = bin_dir / "worktools"
            self.assertEqual(link.resolve(), LAUNCHER.resolve())
            proc = subprocess.run([str(link), "--list"], capture_output=True, text=True)
            self.assertIn("balanced", proc.stdout)
            subprocess.run(base + ["--uninstall"], capture_output=True, text=True, check=True)
            self.assertFalse(link.exists())


if __name__ == "__main__":
    unittest.main()


class StatuslineModeTests(unittest.TestCase):
    def test_mode_shown_first(self):
        sys.path.insert(0, str(REPO / "src" / "plugin" / "worktools" / "scripts" / "usage"))
        import statusline
        old = os.environ.get("CODE_SURVEY_MODE")
        try:
            os.environ["CODE_SURVEY_MODE"] = "balanced"
            self.assertTrue(statusline.render({}).startswith("[balanced]"))
            del os.environ["CODE_SURVEY_MODE"]
            self.assertTrue(statusline.render({}).startswith("[モードなし]"))
        finally:
            if old is not None:
                os.environ["CODE_SURVEY_MODE"] = old


class ReadBudgetTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REPO / "src" / "plugin" / "worktools" / "scripts" / "survey"))
        import read_budget
        self.rb = read_budget
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.transcript = root / "sess.jsonl"
        self.transcript.write_text("")
        subs = root / "sess" / "subagents"
        subs.mkdir(parents=True)
        self.agent_file = subs / "agent-a1.jsonl"
        self.big = root / "big.py"
        self.big.write_text("x = 1\n" * 500)

    def tearDown(self):
        self.tmp.cleanup()

    def usage(self, prompt):
        self.agent_file.write_text(json.dumps({"type": "assistant", "message": {"id": "m", "usage": {
            "input_tokens": 10, "cache_read_input_tokens": prompt - 10,
            "cache_creation_input_tokens": 0}}}) + "\n")

    def call(self, tool="Grep", agent="worktools:surveyor", tool_input=None, env=None):
        payload = {"agent_id": "a1", "agent_type": agent, "tool_name": tool,
                   "transcript_path": str(self.transcript), "tool_input": tool_input or {}}
        return self.rb.decide(payload, env or {})

    def test_main_session_is_never_limited(self):
        self.usage(500_000)
        payload = {"tool_name": "Read", "transcript_path": str(self.transcript),
                   "tool_input": {"file_path": str(self.big)}}
        self.assertIsNone(self.rb.decide(payload, {}))

    def test_budget(self):
        self.usage(50_000)
        self.assertIsNone(self.call())
        self.usage(90_000)
        out = self.call(agent="Explore")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("Reading budget reached", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.call(env={"CODE_SURVEY_SUBAGENT_PROMPT_LIMIT": "0"}))
        self.assertIsNone(self.call(env={"CODE_SURVEY_SUBAGENT_PROMPT_LIMIT": "100000"}))

    def test_whole_file_read(self):
        self.usage(1_000)
        whole = self.call("Read", tool_input={"file_path": str(self.big)})
        self.assertIn("500 lines", whole["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.call("Read", tool_input={"file_path": str(self.big), "offset": 1,
                                                        "limit": 100}))
        self.assertIsNone(self.call("Read", agent="Explore", tool_input={"file_path": str(self.big)}))
