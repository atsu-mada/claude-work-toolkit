"""Tests for the usage scripts. Run: python3 -m unittest discover -s src/test"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
USAGE = REPO / "src" / "plugin" / "worktools" / "scripts" / "usage"
sys.path.insert(0, str(USAGE))

import usage_core as core  # noqa: E402
import statusline  # noqa: E402
import log_hook  # noqa: E402

PRICING = {
    "checked_on": "2026-10-20",
    "multipliers": {"inference_geo": {"global": 1.0, "us": 1.1}},
    "models": {
        "claude-sonnet-5-5": {"input": 2.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0,
                              "cache_read": 0.10, "output": 10.0},
        "claude-haiku-5-5": {"tiers": [
            {"max_prompt_tokens": 100000, "input": 0.10, "cache_write_5m": 0.125,
             "cache_write_1h": 0.20, "cache_read": 0.01, "output": 0.50},
            {"max_prompt_tokens": None, "input": 0.50, "cache_write_5m": 0.625,
             "cache_write_1h": 1.00, "cache_read": 0.05, "output": 2.50}]},
    },
}


def line(msg_id, model, inp=0, out=0, cr=0, cw5=0, cw1h=0, geo="global"):
    return json.dumps({"type": "assistant", "message": {
        "id": msg_id, "model": model, "usage": {
            "input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cw5 + cw1h,
            "cache_creation": {"ephemeral_5m_input_tokens": cw5, "ephemeral_1h_input_tokens": cw1h},
            "inference_geo": geo}}}) + "\n"


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.old_env = dict(os.environ)
        os.environ["CODE_SURVEY_STATE_DIR"] = str(root / "state")
        os.environ["CODE_SURVEY_LOG_DIR"] = str(root / "logs")
        os.environ["CODE_SURVEY_USDJPY"] = "150"
        pricing_path = root / "pricing.json"
        pricing_path.write_text(json.dumps(PRICING))
        os.environ["CODE_SURVEY_PRICING"] = str(pricing_path)
        project = root / "projects" / "-tmp-proj"
        project.mkdir(parents=True)
        self.transcript = project / "sess1.jsonl"
        self.transcript.write_text(
            line("m1", "claude-sonnet-5-5", inp=10, out=1, cw1h=10000)
            + line("m1", "claude-sonnet-5-5", inp=10, out=200, cw1h=10000)  # same id, last wins
            + line("m2", "claude-sonnet-5-5", inp=5, out=100, cr=10000)
            + json.dumps({"type": "assistant", "message": {"id": "s", "model": "<synthetic>",
                                                           "usage": {"input_tokens": 9}}}) + "\n")
        subs = project / "sess1" / "subagents"
        subs.mkdir(parents=True)
        self.agent = subs / "agent-abc.jsonl"
        self.agent.write_text(line("a1", "claude-haiku-5-5", inp=100, out=50, cw5=1000)
                              + line("a2", "claude-haiku-5-5", inp=100, out=50, cr=1000))
        (subs / "agent-abc.meta.json").write_text(json.dumps(
            {"agentType": "code-surveyor", "description": "auth 調査"}))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()


class CoreTests(Env):
    def test_dedupe_last_line_wins_and_skips_synthetic(self):
        rows = core.read_rows(self.transcript, {})["rows"]
        self.assertEqual(set(rows), {"m1", "m2"})
        self.assertEqual(rows["m1"][2], 200)

    def test_incremental_read_waits_for_full_line(self):
        cache = core.read_rows(self.transcript, {})
        offset = cache["offset"]
        partial = line("m3", "claude-sonnet-5-5", inp=1)
        with open(self.transcript, "a") as f:
            f.write(partial[:20])
        core.read_rows(self.transcript, cache)
        self.assertEqual(cache["offset"], offset)
        with open(self.transcript, "a") as f:
            f.write(partial[20:])
        core.read_rows(self.transcript, cache)
        self.assertIn("m3", cache["rows"])

    def test_pricing_tiers_and_geo(self):
        small = ["claude-haiku-5-5", 1_000_000, 0, 0, 0, 0, "global"]
        big = ["claude-haiku-5-5", 200_000, 0, 0, 0, 0, "global"]
        self.assertAlmostEqual(core.row_usd(PRICING, small), 0.50)  # > 100k -> second tier
        self.assertAlmostEqual(core.row_usd(PRICING, ["claude-haiku-5-5", 1000, 0, 0, 0, 0,
                                                      "global"]), 0.0001)
        self.assertAlmostEqual(core.row_usd(PRICING, big), 0.10)
        us = ["claude-sonnet-5-5", 1_000_000, 0, 0, 0, 0, "us"]
        self.assertAlmostEqual(core.row_usd(PRICING, us), 2.2)
        self.assertEqual(core.row_usd(PRICING, ["unknown-model", 5, 5, 5, 5, 5, "global"]), 0.0)

    def test_summarize_parent_and_subagent(self):
        s = core.summarize(str(self.transcript), "sess1")
        self.assertEqual(s["main"]["all"]["requests"], 2)
        self.assertEqual(s["sub"]["all"]["requests"], 2)
        self.assertEqual(s["agents"]["abc"]["type"], "code-surveyor")
        # main hit rate: 10000 read / (15 input + 10000 read + 10000 write)
        self.assertAlmostEqual(s["main"]["all"]["hit_rate"], round(10000 / 20015, 4))
        expected_main = (15 * 2 + 300 * 10 + 10000 * 0.10 + 10000 * 4.0) / 1e6
        self.assertAlmostEqual(s["main"]["all"]["usd"], expected_main, places=6)
        self.assertAlmostEqual(s["total"]["all"]["usd"],
                               s["main"]["all"]["usd"] + s["sub"]["all"]["usd"], places=6)


class PromptSizeTests(unittest.TestCase):
    def test_max_prompt_and_over_100k(self):
        rows = [["claude-haiku-5-5", 10, 1, 90_000, 0, 0, "global"],
                ["claude-haiku-5-5", 10, 1, 95_000, 6_000, 0, "global"]]
        t = core.totals(PRICING, rows)["all"]
        self.assertEqual(t["max_prompt"], 101_010)
        self.assertEqual(t["requests_over_100k"], 1)


class NoteCheckTests(unittest.TestCase):
    SCRIPT = REPO / "src" / "plugin" / "worktools" / "scripts" / "survey" / "check_note.py"

    def run_check(self, agent, path):
        payload = {"agent_type": agent, "tool_input": {"file_path": str(path)}}
        return subprocess.run([sys.executable, str(self.SCRIPT)], input=json.dumps(payload),
                              capture_output=True, text=True)

    def test_bad_note_is_sent_back_good_note_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            bad = notes / "a.json"
            bad.write_text(json.dumps({"module": "x", "summary": "s", "risks": []}))
            proc = self.run_check("worktools:surveyor", bad)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("missing key `findings`", proc.stderr)
            good = notes / "b.json"
            good.write_text(json.dumps({
                "module": "x", "summary": "s", "entry_points": [], "dependencies": {},
                "findings": [{"topic": "t", "detail": "d", "file": "f.py", "line": 3}],
                "answers": [{"question": "q", "answer": "a",
                             "evidence": [{"file": "f.py", "line": 3}]}],
                "open_questions": [], "files_read": ["f.py"]}))
            self.assertEqual(self.run_check("worktools:surveyor", good).returncode, 0)
            # other writers and other files are ignored
            self.assertEqual(self.run_check("general-purpose", bad).returncode, 0)
            self.assertEqual(self.run_check("worktools:surveyor", Path(tmp) / "x.json")
                             .returncode, 0)


class DisplayTests(Env):
    def test_statusline_text_and_snapshot(self):
        payload = {"transcript_path": str(self.transcript), "session_id": "sess1",
                   "model": {"display_name": "Sonnet 5.5", "id": "claude-sonnet-5-5"},
                   "context_window": {"used_percentage": 34.2},
                   "cost": {"total_cost_usd": 0.05},
                   "prompt_cache": {"hit_ratio": 0.93, "misses": 1, "warm": True,
                                    "caching_observed": True,
                                    "last_miss_cause": {"causes": ["tools_changed"]}}}
        text = statusline.render(payload)
        self.assertIn("親 ¥", text)
        self.assertIn("サブ ¥", text)
        self.assertIn("1体", text)
        self.assertIn("キャッシュ 親93%", text)
        self.assertIn("ミス1(tools_changed)", text)
        self.assertIn("ctx 34%", text)
        snap = json.loads((self.root / "state" / "sess1.status.json").read_text())
        self.assertEqual(snap["official_cost_usd"], 0.05)

    def test_subagent_rows(self):
        payload = {"transcript_path": str(self.transcript), "session_id": "sess1",
                   "tasks": [{"id": "abc", "agentType": "code-surveyor",
                              "model": "claude-haiku-5-5", "tokenCount": 84200,
                              "label": "auth 調査"},
                             {"id": "zzz", "agentType": "Explore", "tokenCount": 10}]}
        proc = subprocess.run([sys.executable, str(USAGE / "subagent_statusline.py")],
                              input=json.dumps(payload), capture_output=True, text=True,
                              env=os.environ.copy())
        rows = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in rows], ["abc", "zzz"])
        self.assertIn("code-surveyor · Haiku · 84.2k tok · ¥", rows[0]["content"])
        self.assertIn("キャッシュ", rows[0]["content"])
        self.assertTrue(rows[1]["content"].startswith("Explore"))


class HookTests(Env):
    def run_hook(self, payload):
        proc = subprocess.run([sys.executable, str(USAGE / "log_hook.py")],
                              input=json.dumps(payload), capture_output=True, text=True,
                              env=os.environ.copy())
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_subagent_stop_line(self):
        self.run_hook({"hook_event_name": "SubagentStop", "session_id": "sess1",
                       "cwd": str(self.root), "agent_id": "abc", "agent_type": "code-surveyor",
                       "agent_transcript_path": str(self.agent)})
        rec = json.loads((self.root / "logs" / "subagents.jsonl").read_text().splitlines()[0])
        self.assertEqual(rec["agent_type"], "code-surveyor")
        self.assertEqual(rec["all"]["requests"], 2)
        self.assertAlmostEqual(rec["all"]["hit_rate"], round(1000 / 2200, 4))

    def test_stop_then_session_end(self):
        base = {"session_id": "sess1", "cwd": str(self.root),
                "transcript_path": str(self.transcript)}
        self.run_hook({**base, "hook_event_name": "Stop"})
        snap = json.loads((self.root / "logs" / "sessions" / "sess1.json").read_text())
        self.assertEqual(snap["subagent_count"], 1)
        self.run_hook({**base, "hook_event_name": "SessionEnd", "reason": "prompt_input_exit"})
        rec = json.loads((self.root / "logs" / "sessions.jsonl").read_text().splitlines()[0])
        self.assertEqual(rec["event"], "session_end")
        self.assertEqual(rec["subagent_types"]["code-surveyor"]["count"], 1)
        self.assertGreater(rec["sub_share"], 0)
        dumped = json.dumps(rec)
        self.assertNotIn("auth 調査", json.dumps(rec["subagent_types"]))
        for text_field in ('"prompt":', '"message":', '"content":', "auth 調査"):
            self.assertNotIn(text_field, dumped)

    def test_bad_input_never_fails(self):
        proc = subprocess.run([sys.executable, str(USAGE / "log_hook.py")], input="not json",
                              capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(proc.returncode, 0)


class InstallTests(unittest.TestCase):
    def run_install(self, target, *extra):
        return subprocess.run([sys.executable, str(REPO / "src" / "setup" / "install.py"),
                               "--target", str(target), *extra],
                              capture_output=True, text=True)

    def test_install_keeps_foreign_and_uninstalls(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text(json.dumps({"statusLine": {"type": "command", "command": "mine.sh"},
                                          "env": {"A": "1"}}))
            self.run_install(target)
            data = json.loads(target.read_text())
            self.assertEqual(data["statusLine"]["command"], "mine.sh")
            self.assertIn("subagent_statusline.py", data["subagentStatusLine"]["command"])
            self.run_install(target, "--force")
            data = json.loads(target.read_text())
            self.assertEqual(data["statusLine"]["refreshInterval"], 5)
            self.run_install(target, "--uninstall")
            data = json.loads(target.read_text())
            self.assertEqual(data, {"env": {"A": "1"}})

    def test_profile_set_switch_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text(json.dumps({"env": {"A": "1"}}))
            self.run_install(target, "--profile", "haiku-all", "--no-statusline")
            data = json.loads(target.read_text())
            self.assertEqual(data["model"], "haiku")
            self.assertEqual(data["env"]["CLAUDE_CODE_SUBAGENT_MODEL_FORCE"], "1")
            self.assertNotIn("statusLine", data)
            self.run_install(target, "--profile", "haiku-subagents", "--no-statusline")
            data = json.loads(target.read_text())
            self.assertNotIn("model", data)
            self.assertEqual(data["env"]["CLAUDE_CODE_SUBAGENT_MODEL"], "haiku")
            data["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] = "sonnet"  # user changed it by hand
            target.write_text(json.dumps(data))
            self.run_install(target, "--uninstall")
            data = json.loads(target.read_text())
            self.assertEqual(data, {"env": {"A": "1", "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"}})
            self.assertFalse((Path(tmp) / "settings.json.code-survey.json").exists())


if __name__ == "__main__":
    unittest.main()
