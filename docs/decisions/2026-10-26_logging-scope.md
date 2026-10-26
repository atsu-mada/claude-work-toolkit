# 2026-10-26 Logging scope

- Spend is computed from transcripts, not from OpenTelemetry: OTel has no file exporter and needs a collector.
- Logs stay on each machine (`~/.local/share/code-survey/logs`). Only number-only review summaries may be
  committed later, under `docs/reviews/`.
- The plugin carries the hooks; `src/setup/install.py` writes the status lines, which plugins cannot set.
