# claude-work-toolkit

- Implementation lives in `src/`; tests in `src/test/` (run `python3 -m unittest discover -s src/test`).
- Scripts under `src/plugin/worktools/scripts/` use the standard library only and must run on Python 3.9+.
- Hooks and status line scripts must never fail loudly: hooks exit 0, the status line always prints one line.
- Logs hold numbers and labels only; never write code, prompts, or replies into them.
- Update `src/plugin/worktools/config/pricing.json` from its `source` URL and change `checked_on`.
- Keep runtime data in `data/` (not committed). Design notes go to `docs/`.
- HTML output (the survey report template, any page): invoke `/awesome-design-skills` first and follow it.
