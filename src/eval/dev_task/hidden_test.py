"""Hidden acceptance tests for the review task. Run: python3 hidden_test.py <repo>"""
import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(sys.argv.pop(1)).resolve()
SCRIPT = REPO / "src" / "review" / "review.py"
spec = importlib.util.spec_from_file_location("review", SCRIPT)
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)


def rec(sid, label, usd, hit, share, over=None):
    r = {"session_id": sid, "label": label, "total": {"all": {"usd": usd}},
         "main": {"all": {"hit_rate": hit}}, "sub_share": share}
    if over is not None:
        r["total"]["all"]["requests_over_100k"] = over
    return r


class T(unittest.TestCase):
    def test_grouping_and_rounding(self):
        out = review.summarize([rec("a", "x", 0.11111, 0.9, 0.2, 1), rec("b", "x", 0.22222, 0.8, 0.4, 2)])
        g = out["labels"]["x"]
        self.assertEqual(g["sessions"], 2)
        self.assertEqual(g["usd"], 0.3333)
        self.assertEqual(g["hit_rate_avg"], 0.85)
        self.assertEqual(g["sub_share_avg"], 0.3)
        self.assertEqual(g["requests_over_100k"], 3)

    def test_none_label_nulls_and_missing_over(self):
        out = review.summarize([rec("a", "", 1.0, None, None), {"session_id": "b", "total": {"all": {"usd": 2.0}},
                                "main": {"all": {"hit_rate": None}}, "sub_share": None}])
        g = out["labels"]["(none)"]
        self.assertEqual(g["sessions"], 2)
        self.assertIsNone(g["hit_rate_avg"])
        self.assertIsNone(g["sub_share_avg"])
        self.assertEqual(g["requests_over_100k"], 0)

    def test_flags_order_and_both(self):
        out = review.summarize([rec("a", "x", 0, 0.5, 0.9), rec("b", "", 0, 0.95, 0.1), rec("c", "y", 0, 0.86, 0.61)])
        self.assertEqual(out["flags"], [
            {"session_id": "a", "label": "x", "reason": "low_cache_hit"},
            {"session_id": "a", "label": "x", "reason": "high_sub_share"},
            {"session_id": "c", "label": "y", "reason": "high_sub_share"}])

    def test_thresholds_are_parameters(self):
        out = review.summarize([rec("a", "x", 0, 0.9, 0.5)], hit_floor=0.95, share_ceiling=0.4)
        self.assertEqual([f["reason"] for f in out["flags"]], ["low_cache_hit", "high_sub_share"])
        self.assertEqual(review.summarize([rec("a", "x", 0, 0.85, 0.6)])["flags"], [])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.jsonl"
            p.write_text(json.dumps(rec("a", "x", 0.5, 0.5, 0.1)) + "\n\nnot json\n" + json.dumps(rec("b", "x", 0.5, 0.9, 0.1)) + "\n")
            r = subprocess.run([sys.executable, str(SCRIPT), str(p), "--hit-floor", "0.6"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["labels"]["x"]["sessions"], 2)
            self.assertEqual(out["flags"], [{"session_id": "a", "label": "x", "reason": "low_cache_hit"}])
            r = subprocess.run([sys.executable, str(SCRIPT), str(Path(tmp) / "missing.jsonl")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.strip())


if __name__ == "__main__":
    unittest.main(verbosity=1)
