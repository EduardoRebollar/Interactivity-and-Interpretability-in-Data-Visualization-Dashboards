"""Offline scoring and analysis. **Never ships.**

Everything under `src/` is uploaded to Vercel and much of it reaches the browser, so the answer key
cannot live there. This package is listed in `vercel.json`'s `excludeFiles`;
`tests/test_scoring.py` fails if it stops being excluded, or if any runtime module imports it.

Implements exactly what `docs/study-design.md` section 7 pre-registers -- accuracy, the exclusion
rules, reasoning-depth coding and inter-rater reliability -- and nothing more. Inferential
statistics belong in the analysis notebook, not in the instrument.
"""
