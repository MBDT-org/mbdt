# Contributing to MBDT

Thanks for helping. MBDT exists to make systematic literacy practice feel less
like a worksheet; contributions that keep it accurate, kind to learners and
local-first are welcome.

**Read the disclaimer first.** This project is supplementary practice, not
therapy or medical advice. Please don't open issues or PRs that frame it as a
treatment or claim clinical outcomes.

## Ground rules

- **Never commit learner data.** `backend/mbdt.db*` and `backend/.env` are
  git-ignored. Leave them that way, and never paste a learner's records,
  recordings or names into issues.
- **Never commit an API key.** Use `.env` locally; CI has no provider key and
  the test suite must stay offline.
- **Keep verdicts honest.** Don't tune thresholds or similarity scoring to make
  numbers look better. If a change alters how a correct answer is judged, add a
  test that states the behavior.
- **Accessibility is a feature.** The UI targets children with dyslexia:
  contrast, focus states, touch target size, `prefers-reduced-motion` and the
  Lexend reading stack are not optional.

## Workflow

```bash
uv sync
pnpm install

./dev.sh            # API :8777 + UI :5173
pnpm typecheck
pnpm lint
uv run python backend/test_confidence.py
uv run python backend/test_ocr_clean.py
uv run python backend/test_story_filter.py
uv run python backend/test_providers.py
```

Add a small assertion-based check for non-trivial logic. The backend test file
runs with plain `assert`s — no pytest required — and is also a good template.

## Where things live

| Change | File |
|---|---|
| An exercise's rules, sampling, scoring | `backend/exercises/` |
| Bayesian model, decay, sampling | `backend/algorithm.py` |
| SQLite schema and migrations | `backend/db.py`, `backend/repository.py` |
| Gateway calls, retries, error codes | `backend/services.py` |
| API routes and request models | `backend/app.py` |
| Design tokens, buttons, layout | `frontend/src/index.css` |
| Session flow, stages, breaks | `frontend/src/components/DailySession.tsx` |
| Home path, XP, quests | `frontend/src/components/HomePath.tsx` |
| Dashboard, guardian, admin | `frontend/src/components/Dashboard.tsx` |

## Adding words

For your own vocabulary, drop a JSON file in `backend/data/word_sets/` — see the
[README](README.md#add-your-own-word-set) and
`backend/data/word_sets/README.md`. No code change is required.

To ship a new *built-in* set, add it to `SETS` and `SET_LABELS` in
`backend/data/words.py`. Each entry needs a word and a phoneme bucket; check the
grouping against the accent you are targeting, and keep the source's license
compatible with MIT.

## Pull requests

- One topic per PR, with a short "why" in the description.
- Include before/after screenshots for UI changes.
- Mention any model or prompt change explicitly: prompts are part of the
  safety surface and are reviewed for what they send off-device.
- Update `README.md` when behavior, configuration or setup changes.

## License

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE).
