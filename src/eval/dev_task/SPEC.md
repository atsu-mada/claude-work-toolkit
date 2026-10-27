# Task: usage review script

Add `src/review/review.py` to this repository, plus tests in `src/test/test_review.py`.
Use the Python standard library only. Python 3.9+ syntax.

## Input

A JSON Lines file written by `log_hook.py` (`sessions.jsonl`). Each line is one session record with at
least these keys (see `src/plugin/worktools/scripts/usage/log_hook.py`):
`session_id` (str), `label` (str, may be empty), `total.all.usd` (float),
`main.all.hit_rate` (float or null), `sub_share` (float or null), `total.all.requests_over_100k` (int,
may be missing in old records: treat as 0). Blank lines and lines that are not valid JSON are skipped.

## Function

`summarize(records: list[dict], hit_floor: float = 0.85, share_ceiling: float = 0.6) -> dict` returns:

```json
{
  "labels": {
    "<label or (none)>": {
      "sessions": 2,
      "usd": 0.1234,
      "hit_rate_avg": 0.91,
      "sub_share_avg": 0.4,
      "requests_over_100k": 0
    }
  },
  "flags": [
    {"session_id": "...", "label": "...", "reason": "low_cache_hit"}
  ]
}
```

- Group by `label`; an empty or missing label is grouped as `(none)` (also in flags).
- `usd`: sum, rounded to 4 decimals. Averages: mean of the non-null values, rounded to 4 decimals;
  `null` when there are none.
- Flags, in input order: `low_cache_hit` when `main.all.hit_rate` is not null and `< hit_floor`;
  `high_sub_share` when `sub_share` is not null and `> share_ceiling`. A session can have both
  (two entries, `low_cache_hit` first).

## Command line

`python3 src/review/review.py <path> [--hit-floor F] [--share-ceiling F]` prints the summary as JSON
(`json.dumps(result, ensure_ascii=False, indent=2)`) and exits 0. A missing file: message on stderr,
exit code 1.
