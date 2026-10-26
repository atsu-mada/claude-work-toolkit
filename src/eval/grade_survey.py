"""Grade survey notes mechanically: schema, citations, and answered questions.

Usage: python3 src/eval/grade_survey.py <survey_dir> <target_repo>

A citation is any {file, line} in entry_points, findings, or answers[].evidence.
- file_ok: the file exists in the target repository
- line_ok: the line number is within the file
- name_ok (entry points only): a word of the entry-point name appears within 3 lines of the cited line
Prints one JSON object per note and a total.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KEYS = {"module", "summary", "entry_points", "dependencies", "findings", "answers",
        "open_questions", "files_read"}


def resolve(repo: Path, name: str):
    name = re.sub(r"\s*\(.*\)$", "", str(name)).strip()
    path = Path(name)
    if not path.is_absolute():
        path = repo / path
    return path if path.is_file() else None


def lines_of(path: Path, cache: dict) -> list:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[path]


def check(repo: Path, item: dict, cache: dict, name: str = "") -> dict:
    result = {"file_ok": False, "line_ok": False, "name_ok": None}
    path = resolve(repo, item.get("file") or "")
    if not path:
        return result
    result["file_ok"] = True
    text = lines_of(path, cache)
    try:
        line = int(item.get("line") or 0)
    except (TypeError, ValueError):
        line = 0
    result["line_ok"] = 1 <= line <= len(text)
    if name and result["line_ok"]:
        words = [w for w in re.split(r"\W+", name) if len(w) > 3]
        window = "\n".join(text[max(0, line - 4): line + 3])
        result["name_ok"] = any(w in window for w in words) if words else None
    return result


def grade(note_path: Path, repo: Path) -> dict:
    cache: dict = {}
    try:
        note = json.loads(note_path.read_text(encoding="utf-8"))
    except ValueError:
        return {"note": note_path.name, "valid_json": False}
    cites = []
    for ep in note.get("entry_points") or []:
        if isinstance(ep, dict):
            cites.append(check(repo, ep, cache, ep.get("name") or ""))
    for f in note.get("findings") or []:
        if isinstance(f, dict):
            cites.append(check(repo, f, cache))
    answered = 0
    for a in note.get("answers") or []:
        if not isinstance(a, dict):
            continue
        if (a.get("answer") or "").strip():
            answered += 1
        for ev in a.get("evidence") or []:
            if isinstance(ev, dict):
                cites.append(check(repo, ev, cache))
    names = [c["name_ok"] for c in cites if c["name_ok"] is not None]
    return {
        "note": note_path.name,
        "valid_json": True,
        "schema_ok": set(note) == KEYS,
        "answers": answered,
        "findings": len(note.get("findings") or []),
        "open_questions": len(note.get("open_questions") or []),
        "citations": len(cites),
        "file_ok": sum(c["file_ok"] for c in cites),
        "line_ok": sum(c["line_ok"] for c in cites),
        "entry_name_ok": f"{sum(names)}/{len(names)}",
    }


def main() -> None:
    survey, repo = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    rows = [grade(p, repo) for p in sorted((survey / "notes").glob("*.json"))]
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    total = {k: sum(r.get(k, 0) for r in rows if isinstance(r.get(k), int) and not isinstance(r.get(k), bool))
             for k in ("answers", "findings", "citations", "file_ok", "line_ok", "open_questions")}
    total["notes"] = len(rows)
    total["schema_ok"] = sum(bool(r.get("schema_ok")) for r in rows)
    print(json.dumps({"total": total}))


if __name__ == "__main__":
    main()
