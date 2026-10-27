#!/usr/bin/env python3
"""Build one self-contained HTML report from a survey folder.

Usage:
  python3 render_report.py <survey_dir> [--out report.html] [--source-url URL] [--title TEXT]

<survey_dir> holds summary.json and notes/*.json (written by the survey skill and the surveyor agent).
--source-url turns every file:line into a link, e.g. https://github.com/org/repo/blob/main/
(the link becomes <url><path>#L<line>). Without it, locations are shown as text.

No model tokens are used: the report is assembled from the JSON files. The HTML has no external
resources except the Open Sans / JetBrains Mono web fonts (falls back to system fonts offline),
follows the awesome-design-skills system, and fits phone screens.
Standard library only; Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

CONFIG_TOPICS = {
    "config-key": ("読まれている", "ok"),
    "config-key-unused": ("使われていない", "warn"),
    "config-key-ignored": ("直書きで無視", "bad"),
}


# ---------- loading ----------

def load_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_survey(folder: Path) -> tuple:
    summary = load_json(folder / "summary.json", {})
    notes = []
    for path in sorted((folder / "notes").glob("*.json")):
        note = load_json(path, None)
        if isinstance(note, dict):
            note.setdefault("_slug", path.stem)
            notes.append(note)
    return (summary if isinstance(summary, dict) else {}), notes


def as_list(value) -> list:
    if isinstance(value, list):
        return value
    return [] if value in (None, "") else [value]


def text(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


# ---------- rendering helpers ----------

class Ctx:
    def __init__(self, repo: str, source_url: str):
        self.repo = repo.rstrip("/") + "/" if repo else ""
        self.source_url = source_url

    def rel(self, path: str) -> str:
        path = text(path).strip()
        if self.repo and path.startswith(self.repo):
            return path[len(self.repo):]
        return path

    def loc(self, file, line=None) -> str:
        """file:line as code text, or as a link when --source-url is given."""
        if not file:
            return ""
        rel = self.rel(file)
        label = f"{rel}:{line}" if line else rel
        if self.source_url and not rel.startswith("/") and " " not in rel:
            href = self.source_url + rel + (f"#L{line}" if line else "")
            return f'<a class="loc" href="{html.escape(href)}">{html.escape(label)}</a>'
        return f'<code class="loc">{html.escape(label)}</code>'


def esc(value) -> str:
    return html.escape(text(value))


def badge(label: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{html.escape(label)}</span>'


def confidence_badge(value) -> str:
    value = text(value).lower()
    kind = {"high": "ok", "medium": "", "low": "warn"}.get(value, "")
    names = {"high": "確度 高", "medium": "確度 中", "low": "確度 低"}
    return badge(names.get(value, value), kind) if value else ""


# ---------- sections ----------

def stats(summary: dict, notes: list) -> str:
    findings = [f for n in notes for f in as_list(n.get("findings")) if isinstance(f, dict)]
    unused = sum(1 for f in findings if f.get("topic") == "config-key-unused")
    ignored = sum(1 for f in findings if f.get("topic") == "config-key-ignored")
    opens = sum(len(as_list(n.get("open_questions"))) for n in notes)
    items = [("モジュール", len(notes)), ("発見", len(findings)),
             ("リスク", len(as_list(summary.get("risks")))), ("未解決の疑問", opens),
             ("未使用の設定", unused), ("無視される設定", ignored)]
    cells = "".join(f'<div class="stat"><div class="num">{v}</div><div class="lbl">{k}</div></div>'
                    for k, v in items)
    return f'<section class="stats">{cells}</section>'


def overview(summary: dict, notes: list, ctx: Ctx) -> str:
    parts = [f'<section><h2>概要</h2><p class="lead">{esc(summary.get("overview"))}</p>']
    mods = as_list(summary.get("modules")) or [{"slug": n["_slug"], "summary": n.get("summary")}
                                               for n in notes]
    rows = "".join(f'<tr><td><a href="#m-{esc(m.get("slug"))}">{esc(m.get("slug"))}</a></td>'
                   f'<td>{esc(m.get("summary"))}</td></tr>' for m in mods if isinstance(m, dict))
    if rows:
        parts.append(f'<h3>モジュール</h3><div class="scroll"><table><thead><tr><th>名前</th>'
                     f'<th>役割</th></tr></thead><tbody>{rows}</tbody></table></div>')
    cross = [c for c in as_list(summary.get("cross_module")) if isinstance(c, dict)]
    if cross:
        rows = "".join(f'<tr><td>{esc(c.get("from"))}</td><td>{esc(c.get("to"))}</td>'
                       f'<td>{esc(c.get("how"))}</td></tr>' for c in cross)
        parts.append(f'<h3>モジュール間のつながり</h3><div class="scroll"><table><thead><tr>'
                     f'<th>から</th><th>へ</th><th>どのように</th></tr></thead><tbody>{rows}'
                     f'</tbody></table></div>')
    for key, title in (("risks", "リスク"), ("open_questions", "未解決の疑問")):
        items = as_list(summary.get(key))
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            parts.append(f'<h3>{title}</h3><ul class="{key}">{lis}</ul>')
    parts.append("</section>")
    return "".join(parts)


def answers_block(note: dict, ctx: Ctx) -> str:
    items = [a for a in as_list(note.get("answers")) if isinstance(a, dict)]
    if not items:
        return ""
    out = []
    for a in items:
        ev = " ".join(ctx.loc(e.get("file"), e.get("line")) for e in as_list(a.get("evidence"))
                      if isinstance(e, dict))
        out.append(f'<div class="qa"><div class="q">Q. {esc(a.get("question"))}</div>'
                   f'<div class="a">{esc(a.get("answer"))}</div>'
                   + (f'<div class="ev">根拠 {ev}</div>' if ev else "") + "</div>")
    return "<h3>質問と回答</h3>" + "".join(out)


def entry_points_block(note: dict, ctx: Ctx) -> str:
    items = [e for e in as_list(note.get("entry_points")) if isinstance(e, dict)]
    if not items:
        return ""
    rows = "".join(f'<tr><td><code>{esc(e.get("name"))}</code></td>'
                   f'<td class="where">{ctx.loc(e.get("file"), e.get("line"))}</td></tr>' for e in items)
    return (f'<h3>入口</h3><div class="scroll"><table><thead><tr><th>名前</th><th>場所</th></tr>'
            f'</thead><tbody>{rows}</tbody></table></div>')


def findings_block(note: dict, ctx: Ctx) -> str:
    items = [f for f in as_list(note.get("findings")) if isinstance(f, dict)]
    config = [f for f in items if f.get("topic") in CONFIG_TOPICS]
    other = [f for f in items if f.get("topic") not in CONFIG_TOPICS]
    out = []
    if other:
        rows = "".join(
            f'<tr class="finding"><td>{badge(text(f.get("topic")))}</td>'
            f'<td>{esc(f.get("detail"))}</td><td class="where">{ctx.loc(f.get("file"), f.get("line"))}</td>'
            f'<td>{confidence_badge(f.get("confidence"))}</td></tr>' for f in other)
        out.append(f'<h3>発見</h3><div class="scroll"><table><thead><tr><th>分類</th><th>内容</th>'
                   f'<th>場所</th><th>確度</th></tr></thead><tbody>{rows}</tbody></table></div>')
    if config:
        order = ["config-key-ignored", "config-key-unused", "config-key"]  # problems first
        config.sort(key=lambda f: order.index(f.get("topic")))
        rows = "".join(
            f'<tr class="finding"><td>{badge(*CONFIG_TOPICS[f.get("topic")])}</td>'
            f'<td>{esc(f.get("detail"))}</td><td class="where">{ctx.loc(f.get("file"), f.get("line"))}</td></tr>'
            for f in config)
        out.append(f'<h3>設定項目</h3><div class="scroll"><table><thead><tr><th>状態</th>'
                   f'<th>内容</th><th>場所</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return "".join(out)


def misc_block(note: dict, ctx: Ctx) -> str:
    out = []
    deps = note.get("dependencies")
    if isinstance(deps, dict) and any(deps.values()):
        lis = "".join(f'<li><b>{"内部" if k == "internal" else "外部" if k == "external" else esc(k)}'
                      f'</b> {", ".join(esc(x) for x in as_list(v))}</li>'
                      for k, v in deps.items() if v)
        out.append(f"<h3>依存</h3><ul>{lis}</ul>")
    opens = as_list(note.get("open_questions"))
    if opens:
        out.append("<h3>未解決の疑問</h3><ul>" + "".join(f"<li>{esc(q)}</li>" for q in opens) + "</ul>")
    files = as_list(note.get("files_read"))
    if files:
        lis = "".join(f"<li>{ctx.loc(f) if ' ' not in text(f) else esc(ctx.rel(f))}</li>" for f in files)
        out.append(f'<details><summary>読んだファイル（{len(files)}）</summary><ul class="files">'
                   f'{lis}</ul></details>')
    return "".join(out)


def module_section(note: dict, ctx: Ctx) -> str:
    slug = note["_slug"]
    return (f'<section class="module" id="m-{esc(slug)}"><h2>{esc(slug)}</h2>'
            f'<p class="path">{esc(ctx.rel(note.get("module")))}</p>'
            f'<p>{esc(note.get("summary"))}</p>'
            + answers_block(note, ctx) + entry_points_block(note, ctx) + findings_block(note, ctx)
            + misc_block(note, ctx) + "</section>")


CSS = """
/* awesome-design-skills system: white surface, black as the only fill and divider, pill controls,
   no shadows or gradients, status colors only as border and dot (text stays --text for AA contrast). */
:root{--primary:#000000;--secondary:#ffffff;--surface:#ffffff;--text:#111827;--muted:#4b5563;
--line:#000000;--success:#16a34a;--warning:#d97706;--danger:#dc2626;--r-sm:4px;--r-md:8px;
--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;
--sans:"Open Sans","Hiragino Sans","Noto Sans JP",system-ui,sans-serif;
--mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,monospace}
*{box-sizing:border-box}
html,body{margin:0;background:var(--surface);color:var(--text);font:400 16px/1.6 var(--sans)}
main{max-width:1040px;margin:0 auto;padding:var(--s6) var(--s4) 64px}
header h1{font:700 32px/1.25 var(--sans);margin:0 0 var(--s2);letter-spacing:-.01em}
.caps{font:500 12px/1.4 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
nav{position:sticky;top:0;z-index:2;background:var(--surface);border-bottom:1px solid var(--line);
padding:var(--s3) 0;margin:var(--s5) 0;display:flex;gap:var(--s2);flex-wrap:wrap;align-items:center}
nav a{display:inline-flex;align-items:center;height:32px;padding:0 var(--s4);border:1px solid var(--primary);
border-radius:999px;color:var(--primary);text-decoration:none;font:600 14px/1 var(--sans)}
nav a:hover,a.loc:hover{text-decoration:underline;text-underline-offset:3px}
nav input{margin-left:auto;flex:1 1 200px;max-width:320px;min-width:0;height:36px;padding:0 var(--s4);
border:1px solid var(--primary);border-radius:999px;background:var(--secondary);color:var(--text);font:400 14px var(--sans)}
a:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--primary);outline-offset:3px}
section{border-top:1px solid var(--line);padding:var(--s5) 0;margin:0}
h2{font:700 24px/1.3 var(--sans);margin:0 0 var(--s3)}
h3{font:600 14px/1.4 var(--sans);margin:var(--s5) 0 var(--s2);text-transform:none}
p{margin:0 0 var(--s3)}.lead{font-size:16px}
.path,.meta{font:500 12px/1.5 var(--mono);color:var(--muted);overflow-wrap:anywhere}
td.where{min-width:220px;width:30%}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:var(--s2);border-top:0;padding:0 0 var(--s5)}
.stat{background:var(--primary);color:var(--secondary);border-radius:var(--r-md);padding:var(--s4)}
.stat .num{font:700 32px/1.1 var(--sans);font-variant-numeric:tabular-nums}
.stat .lbl{font:500 12px/1.4 var(--sans);margin-top:var(--s1)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;vertical-align:top;padding:var(--s2) var(--s3) var(--s2) 0;border-bottom:1px solid var(--line)}
th{font:500 12px/1.4 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);white-space:nowrap}
code,.loc{font:400 12px/1.5 var(--mono);overflow-wrap:anywhere}
a.loc{color:var(--primary);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px}
.badge{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border:1px solid var(--primary);
border-radius:999px;font:600 12px/1 var(--sans);white-space:nowrap;color:var(--text);background:var(--secondary)}
.badge.ok,.badge.warn,.badge.bad{border-width:2px}
.badge.ok{border-color:var(--success)}.badge.warn{border-color:var(--warning)}.badge.bad{border-color:var(--danger)}
.badge.ok::before,.badge.warn::before,.badge.bad::before{content:"";width:8px;height:8px;border-radius:50%}
.badge.ok::before{background:var(--success)}.badge.warn::before{background:var(--warning)}.badge.bad::before{background:var(--danger)}
.qa{border-left:2px solid var(--line);padding:var(--s1) 0 var(--s1) var(--s4);margin:var(--s4) 0}
.qa .q{font-weight:700;margin-bottom:var(--s1)}
.qa .ev{font-size:12px;color:var(--muted);margin-top:var(--s2)}
ul{padding-left:1.2em;margin:0}li{margin:var(--s1) 0}
ul.risks li::marker{color:var(--danger)}
details{margin-top:var(--s4)}
summary{cursor:pointer;font:600 14px/1 var(--sans);display:inline-flex;align-items:center;height:32px;
padding:0 var(--s4);border:1px solid var(--primary);border-radius:999px}
.files{columns:2;font-size:12px;margin-top:var(--s3)}
footer{border-top:1px solid var(--line);padding-top:var(--s4);font:500 12px/1.4 var(--mono);color:var(--muted)}
.hidden{display:none}
@media (max-width:640px){header h1{font-size:24px}.files{columns:1}nav input{max-width:none;margin-left:0}}
"""

JS = """
const box=document.getElementById('filter');
box.addEventListener('input',()=>{const q=box.value.trim().toLowerCase();
document.querySelectorAll('tr.finding,.qa').forEach(el=>{
el.classList.toggle('hidden',q!==''&&!el.textContent.toLowerCase().includes(q));});});
"""


def render(summary: dict, notes: list, source_url: str = "", title: str = "") -> str:
    repo = text(summary.get("repository"))
    ctx = Ctx(repo, source_url)
    name = title or (Path(repo).name if repo else "コード調査")
    date = text(summary.get("date")) or datetime.now().strftime("%Y-%m-%d")
    nav = "".join(f'<a href="#m-{esc(n["_slug"])}">{esc(n["_slug"])}</a>' for n in notes)
    body = (f'<header><h1>{esc(name)} 調査レポート</h1>'
            f'<div class="meta">{esc(date)} · {esc(repo)}</div></header>'
            f'<nav><a href="#top">概要</a>{nav}'
            f'<input id="filter" type="search" placeholder="発見と回答を絞り込む" aria-label="絞り込み"></nav>'
            + stats(summary, notes) + overview(summary, notes, ctx)
            + "".join(module_section(n, ctx) for n in notes)
            + f'<footer>claude-work-toolkit で作成 · {len(notes)} モジュール · '
              f'{datetime.now().strftime("%Y-%m-%d %H:%M")}</footer>')
    return ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700"
            "&family=JetBrains+Mono:wght@400;500&display=swap\">"
            f"<title>{esc(name)} 調査レポート</title><style>{CSS}</style></head>"
            f'<body><main id="top">{body}</main><script>{JS}</script></body></html>')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("survey_dir")
    parser.add_argument("--out", help="default: <survey_dir>/report.html")
    parser.add_argument("--source-url", default="", help="base URL for file links")
    parser.add_argument("--title", default="")
    args = parser.parse_args()
    folder = Path(args.survey_dir).expanduser()
    summary, notes = load_survey(folder)
    if not notes and not summary:
        print(f"render_report: no summary.json or notes/*.json in {folder}", file=sys.stderr)
        return 1
    url = args.source_url
    if url and not url.endswith("/"):
        url += "/"
    out = Path(args.out).expanduser() if args.out else folder / "report.html"
    out.write_text(render(summary, notes, url, args.title), encoding="utf-8")
    print(f"report: {out} ({len(notes)} modules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
