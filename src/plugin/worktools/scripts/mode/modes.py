"""Model modes of claude-work-toolkit (defined in config/modes.json).

A mode fixes the main model and the subagent model for a whole session. It is chosen at start because
changing models mid-session rebuilds the prompt cache, and the subagent model cannot change mid-session.
"""

from __future__ import annotations

import json
from pathlib import Path

MODES_FILE = Path(__file__).resolve().parents[2] / "config" / "modes.json"
ENV_MODE = "CODE_SURVEY_MODE"


def load() -> dict:
    with open(MODES_FILE, encoding="utf-8") as f:
        return json.load(f)["modes"]


def resolve(name: str, modes: dict | None = None):
    """Return the canonical mode name for a name or alias (case-insensitive), else None."""
    modes = modes if modes is not None else load()
    key = (name or "").strip().lower()
    for mode, spec in modes.items():
        if key == mode or key in [a.lower() for a in spec.get("aliases", [])]:
            return mode
    return None


def settings_for(mode: str, modes: dict | None = None) -> dict:
    """Settings passed to `claude --settings` for this mode."""
    spec = (modes if modes is not None else load())[mode]
    return {
        "model": spec["model"],
        "env": {
            "CLAUDE_CODE_SUBAGENT_MODEL": spec["subagent_model"],
            # without FORCE the built-in Explore keeps the main model (measured 2026-10-26)
            "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
            ENV_MODE: mode,
        },
    }


def describe(modes: dict | None = None) -> list:
    modes = modes if modes is not None else load()
    return [f"{name:<9} {spec['title']} - {spec['summary']} (aliases: {', '.join(spec.get('aliases', []))})"
            for name, spec in modes.items()]
