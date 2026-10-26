Survey the repository in the current directory with the `code-survey:survey` skill.
Do NOT re-plan the modules: use exactly these three modules, slugs, and questions.

1. slug `core`, module `src/core/`
   - What does `copy_with_renamed_folders` do, step by step?
   - How are duplicate files detected, and where do duplicates go?
   - How is the date of a file determined (sources and their priority)?
2. slug `entrypoints`, module: the root scripts `00_*.py`..`03_*.py` and `src/entrypoints/`
   - What does each stage 00, 01, 02, 03 do (input, output)?
   - How does stage 00 verify that an upload succeeded?
   - Which environment variables or config keys control the stages?
3. slug `config`, module `config/` and `src/utils/`
   - Where are filesystem paths configured, and how are they loaded at runtime?
   - Which keys exist in `config/config.json`, and what does each control?

Write the notes to OUTDIR/notes/<slug>.json and the summary to OUTDIR/summary.json.
Do not modify the repository. Reply with the overview only.
