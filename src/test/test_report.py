"""Tests for the survey HTML report renderer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "src" / "plugin" / "worktools" / "skills" / "survey" / "scripts" / "render_report.py"
sys.path.insert(0, str(SCRIPT.parent))
import render_report as rr  # noqa: E402

NOTE = {
    "module": "/repo/src/core", "summary": "Core <pipeline> & helpers",
    "entry_points": [{"name": "run", "file": "/repo/src/core/main.py", "line": 10}],
    "dependencies": {"internal": ["src/util"], "external": ["rclone"]},
    "findings": [
        {"topic": "risk", "detail": "deletes <dst>", "file": "src/core/main.py", "line": 20,
         "confidence": "low"},
        {"topic": "config-key-unused", "detail": "date_format not read", "file": "config/c.json",
         "line": 3},
        {"topic": "config-key", "detail": "backend read", "file": "src/core/main.py", "line": 5},
    ],
    "answers": [{"question": "What?", "answer": "Copies files",
                 "evidence": [{"file": "/repo/src/core/main.py", "line": 12}]}],
    "open_questions": ["why?"], "files_read": ["/repo/src/core/main.py", "Grep-only: imports"],
}
SUMMARY = {"repository": "/repo", "date": "2026-10-27", "overview": "Overview <b>x</b>",
           "modules": [{"slug": "core", "summary": "core part"}],
           "cross_module": [{"from": "core", "to": "util", "how": "imports"}],
           "risks": ["data loss"], "open_questions": []}


class RenderTests(unittest.TestCase):
    def render(self, **kw):
        return rr.render(SUMMARY, [dict(NOTE, _slug="core")], **kw)

    def test_escapes_and_relative_paths(self):
        out = self.render()
        self.assertIn("Overview &lt;b&gt;x&lt;/b&gt;", out)
        self.assertIn("deletes &lt;dst&gt;", out)
        self.assertNotIn("<b>x</b>", out)
        self.assertIn("src/core/main.py:10", out)
        self.assertNotIn("/repo/src/core/main.py:10", out)

    def test_sections_and_counts(self):
        out = self.render()
        self.assertIn('id="m-core"', out)
        self.assertIn("使われていない", out)
        self.assertIn("読まれている", out)
        self.assertLess(out.index("badge warn\">使われていない"), out.index("badge ok\">読まれている"))
        self.assertIn('<div class="num">1</div><div class="lbl">未使用の設定</div>', out)
        self.assertIn("確度 低", out)
        self.assertIn("data loss", out)

    def test_source_links(self):
        out = self.render(source_url="https://example.com/org/repo/blob/main/")
        self.assertIn('href="https://example.com/org/repo/blob/main/src/core/main.py#L10"', out)
        self.assertIn("Grep-only: imports", out)  # not turned into a link

    def test_tolerates_missing_keys(self):
        out = rr.render({}, [{"_slug": "x", "summary": "only a summary", "findings": "oops"}])
        self.assertIn("only a summary", out)
        self.assertIn("<!doctype html>", out)

    def test_design_tokens(self):
        out = self.render()
        self.assertIn("--primary:#000000", out)
        self.assertIn("border-radius:999px", out)
        self.assertNotIn("box-shadow", out)
        self.assertNotIn("gradient(", out)


class CliTests(unittest.TestCase):
    def test_writes_report_and_fails_on_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            proc = subprocess.run([sys.executable, str(SCRIPT), str(folder)], capture_output=True,
                                  text=True)
            self.assertEqual(proc.returncode, 1)
            (folder / "notes").mkdir()
            (folder / "notes" / "core.json").write_text(json.dumps(NOTE))
            (folder / "summary.json").write_text(json.dumps(SUMMARY))
            proc = subprocess.run([sys.executable, str(SCRIPT), str(folder)], capture_output=True,
                                  text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((folder / "report.html").read_text().startswith("<!doctype html>"))


class AutoReportTests(unittest.TestCase):
    HOOK = REPO / "src" / "plugin" / "worktools" / "scripts" / "survey" / "auto_report.py"

    def run_hook(self, path):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(path)}}
        return subprocess.run([sys.executable, str(self.HOOK)], input=json.dumps(payload),
                              capture_output=True, text=True)

    def test_builds_report_only_for_survey_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "summary.json").write_text(json.dumps(SUMMARY))
            self.assertEqual(self.run_hook(folder / "summary.json").stdout, "")  # no notes/ yet
            (folder / "notes").mkdir()
            (folder / "notes" / "core.json").write_text(json.dumps(NOTE))
            proc = self.run_hook(folder / "summary.json")
            self.assertIn("HTML report written", proc.stdout)
            self.assertTrue((folder / "report.html").exists())
            self.assertEqual(self.run_hook(folder / "other.json").stdout, "")


if __name__ == "__main__":
    unittest.main()
