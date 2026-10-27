---
name: repo-layout-policy
description: Enforce repository layout and file-placement policy to minimize root-level clutter and keep work organized under clear subdirectories. Use when creating a new repository, adding files, changing structure, cleaning root contents, or reorganizing directory trees.
---

# Repo Layout Policy

<!-- Public copy bundled with code-survey-kit. Source: the author's private skill library, without its personal-vault exception. -->

## Objective
- Keep repositories organized by default.
- Avoid adding new files at repository root unless explicitly allowed as an exception.
- Create and use clear subdirectories before creating files.
- Keep test scripts under `src/test/` as a standard subdirectory beneath `src/`.

## Highest-Priority Rules
1. Do not place new files directly under repository root whenever possible.
2. Organize files under purpose-based subdirectories and add lower-level folders when needed.

## Required First-Level Directories
Ensure these directories exist at repository root:
- `config/` for shared configuration
- `data/` for generated outputs, artifacts, and runtime logs under `data/logs/`
- `docs/` for requirements and documentation
- `src/` for implementation code
- `old/` for archived legacy assets

## Root Placement Policy
### Default
- Place every new file under one of: `config/`, `data/`, `docs/`, `src/`, `old/`.
- Treat root placement as an exception only.
- Do not use temporary root placement.

### Allowed Root Exceptions (minimum only)
- `README.md` (thin entrypoint with links to `docs/`)
- `LICENSE` (only when needed)
- `.gitignore` (only when needed)
- `.gitattributes` / `.editorconfig` (only when needed)
- Thin wrapper entrypoints only when they are lightweight launchers for implementation under `src/` or similarly non-root code locations, and do not contain substantial business logic or long processing bodies (e.g., `01_run_manual_prep_flow.py`)
- Agent-facing root markdown only when the file is directly consumed by Claude Code, Codex, or similar agents as an operational instruction file (e.g., `AGENTS.md`, `CLAUDE.md`)
- Dependency manifests required for install/build/run workflows (e.g., `requirements.txt`, `package.json`, `pyproject.toml`, `go.mod`)

For any other file, do not place it at root.

## Placement Decision Flow
- Implementation code -> `src/`
- Test scripts -> `src/test/`
- Thin wrapper entrypoints that only call into implementation under `src/` or equivalent non-root code locations -> root exception
- Configuration -> `config/`
- Agent-facing instruction markdown directly consumed by Claude Code, Codex, or similar agents -> root exception
- Documentation (requirements/spec/design/procedures/memos/decision logs, including human-maintained operational notes such as To-Do lists, backlog notes, future tasks, and personal worklists) -> `docs/`
- To-Do / backlog / future task notes that a human will continue updating -> `docs/todo/` (example: `docs/todo/future-tasks.md`)
- Generated artifacts / intermediate output -> `data/`
- Runtime logs -> `data/logs/`
- Archived legacy assets -> `old/`

If classification is unclear, create a short policy memo under `docs/` first, then classify.

## Log Filename Readability
- When runtime logs or other generated artifacts include a timestamp in the filename, prefer the readable format `YYYY-MM-DD_HH-MM-SS`.
- This is a filename readability recommendation only; it does not change placement rules such as keeping runtime logs under `data/logs/`.

## Subdirectory Governance
- If a first-level directory mixes purposes, grows too large, or becomes hard to navigate, create lower-level folders.
- Split guideline:
  - Consider splitting when a folder has more than 10-20 direct children.
  - Splitting is mandatory when direct children exceed 30.
- Prefer splitting by purpose/use case first, then by artifact type.
- Use explicit names that are understandable without extra context.
- Avoid excessive abbreviations.

### Common `docs/` Subdirectories
- Use `docs/todo/` for human-maintained To-Do documents, backlog notes, future task lists, and similar work-in-progress planning notes.
- Prefer clear task-oriented names in that folder. Example: `docs/todo/future-tasks.md`.
- Do not treat `docs/todo/` examples as fixed filenames; choose a specific name that matches the document's scope.

## Commit Policy
- Do not commit `data/logs/` by default.
- Do not commit `data/` by default, except share-required samples.
- Exclude OS/IDE generated files (e.g., `.DS_Store`, `.vscode`).
- If exceptions are needed, record reason in `docs/`.

## README Policy
- Keep root `README.md` minimal.
- Put detailed setup/operations/spec/design/decision rationale under `docs/`.
- Link from `README.md` to `docs/` details.

## Post-Work Reporting Requirements
Include all four items (order and wording may vary):
1. Confirm that `config/`, `data/`, `docs/`, `src/`, `old/` exist at first level.
2. List current root-level files concisely.
3. If any allowed root exceptions were used, provide one-line reason for each.
   - State which exception class applies: `thin wrapper`, `agent-facing file`, `dependency manifest`, or another explicitly allowed exception.
4. If unnecessary root files existed, report their relocation and required reference/path/link updates.

## Prohibited Actions
- Adding ambiguous-purpose files at root.
- Placing test scripts at root or under ambiguous non-standard locations instead of `src/test/`.
- Using the thin-wrapper exception to place implementation-heavy code or primary business logic at root.
- Using the agent-facing markdown exception for general documentation, specs, or memo files that belong in `docs/`.
- Placing human-maintained To-Do or backlog documents under `data/` or at root when `docs/todo/` is the appropriate location.
- Leaving oversized mixed-purpose folders un-split.
- Committing `data/` (including `data/logs/`) without clear necessity and documented exception rationale.
