#!/bin/zsh
# Run the survey task and the dev task under one model configuration.
# Usage: src/eval/run_config.sh <A|B|C> <survey-target-repo>
#   A: main Sonnet, every subagent Sonnet
#   B: main Sonnet, every subagent Haiku
#   C: main Haiku,  every subagent Haiku
# Output: data/eval/<run>/<cfg>/ (survey notes, dev clone, claude -p JSON results, usage logs)
set -u
CFG=$1
TARGET=$(cd "$2" && pwd)
KIT=$(cd "$(dirname "$0")/../.." && pwd)
RUN=${EVAL_RUN:-$(date +%Y-%m-%d_%H-%M-%S)}
OUT=$KIT/data/eval/$RUN/$CFG
mkdir -p "$OUT/survey" "$OUT/logs"

case $CFG in
  A) MAIN=sonnet; SUB=sonnet; MODE=eval-all-sonnet ;;
  B) MAIN=sonnet; SUB=haiku;  MODE=balanced ;;
  C) MAIN=haiku;  SUB=haiku;  MODE=eco ;;
  *) echo "unknown config $CFG" >&2; exit 2 ;;
esac
SETTINGS=$OUT/settings.json
printf '{"env":{"CLAUDE_CODE_SUBAGENT_MODEL":"%s","CLAUDE_CODE_SUBAGENT_MODEL_FORCE":"1","CODE_SURVEY_MODE":"%s"}}\n' "$SUB" "$MODE" > "$SETTINGS"
export CODE_SURVEY_STATE_DIR=$OUT/state CODE_SURVEY_LOG_DIR=$OUT/logs

# survey
SURVEY_PROMPT=$(sed "s|OUTDIR|$OUT/survey|g" "$KIT/src/eval/survey_task.md")
(cd "$TARGET" && CODE_SURVEY_LABEL=survey-$CFG claude -p --model $MAIN --settings "$SETTINGS" \
  --plugin-dir "$KIT/src/plugin/code-survey" --add-dir "$OUT/survey" \
  --allowedTools "Agent,Glob,Grep,Read,Write($OUT/survey/**),Bash(git ls-files*),Bash(python3 *),Skill" \
  --output-format json "$SURVEY_PROMPT" > "$OUT/survey_result.json" 2> "$OUT/survey_stderr.txt")

# dev (skip with SKIP_DEV=1)
[ "${SKIP_DEV:-0}" = 1 ] && { echo "done $CFG (survey only) -> $OUT"; exit 0; }
git clone -q --branch develop "$KIT" "$OUT/dev-repo"
cp "$KIT/src/eval/dev_task/SPEC.md" "$OUT/dev-repo/TASK.md"
(cd "$OUT/dev-repo" && CODE_SURVEY_LABEL=dev-$CFG claude -p --model $MAIN --settings "$SETTINGS" \
  --plugin-dir "$KIT/src/plugin/code-survey" --permission-mode acceptEdits \
  --allowedTools "Agent,Glob,Grep,Read,Edit,Write,Bash(python3 *),Bash(ls *)" \
  --output-format json "Implement the task described in TASK.md. Run your tests before you finish. Do not commit." \
  > "$OUT/dev_result.json" 2> "$OUT/dev_stderr.txt")
echo "done $CFG -> $OUT"
