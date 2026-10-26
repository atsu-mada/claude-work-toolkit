# 2026-10-26 Quality by model configuration

One run per configuration (n = 1), Claude Code 2.1.310, run with `src/eval/run_config.sh`.
Survey target: 05_image_processor (43k lines), 3 fixed modules, 8 fixed questions (`src/eval/survey_task.md`).
Dev task: `src/eval/dev_task/SPEC.md` (usage review script), graded by 5 hidden tests.
Quality was judged blind by Opus (labels X/Y/Z, mapping kept out of the judge's view): the survey judge
established ground truth from the code and scored each answer 0-2 for correctness and completeness; the
dev judge probed edge cases beyond the hidden tests.

| | A: all Sonnet | B: Sonnet + Haiku subagents | C: all Haiku |
| --- | --- | --- | --- |
| Survey cost / time | $0.93 / 39 s | $0.52 / 87 s | **$0.068** / 154 s |
| Survey score (of 32) | 26 | 26 | **27** |
| Summary usefulness (of 5) | 4 | 3 | 4 |
| Citations in range (mechanical) | 87/87 | 84/84 | 136/136 |
| Citations that support the claim (judge sample) | 13/14 | 10/12 | 12/13 |
| Dev cost / time | $0.27 / 53 s | $0.26 / 48 s | **$0.018** / 37 s |
| Hidden tests | 5/5 | 5/5 | 5/5 |
| Dev review (of 20) | 13 | **16** | 15 |

Notes
- No quality loss from Haiku was visible at this task size. Differences of 1-3 points are within the noise
  of a single run and a single judge.
- Each configuration made 2-4 factual errors in the survey. All three described config keys from their
  names without checking whether the code reads them (most were dead). This is a method gap, not a model gap.
- C (all Haiku) wrote the most thorough tests but crashed on a record with a non-dict nested value; A had
  the weakest tests. All three missed invalid UTF-8 and read the whole file into memory.
- In B one Haiku surveyor reached a 178k-token prompt and cost $0.15 (5x tier above 100k); the other
  surveyors cost $0.005-0.013. The 80k instruction is not enforced.
- Haiku runs took longer (more turns) but cost 8-15x less.

Limits: one repository, one easy dev task, one run each, one judge. Repeat before relying on small gaps.
