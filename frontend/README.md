# Frontend

React 19 + TypeScript + Vite. The app talks to the FastAPI backend under `/api`
(proxied to `:8777` in development by `vite.config.ts`).

```bash
pnpm dev         # Vite dev server on :5173
pnpm typecheck   # tsc project build, no emit
pnpm lint        # eslint
pnpm build       # production bundle in ../dist/
```

## Shape of the UI

```
src/
  App.tsx              shell: header HUD, auth, home, setup, daily routing
  api.ts               typed fetch client for every backend route
  index.css            design tokens + all component styling
  useRecorder.ts       MediaRecorder wrapper for Exercise 1
  components/
    HomePath.tsx       lesson path, XP/level widgets, daily quests, mastery ring
    DailySession.tsx   stage machine: 4 activities, breaks, stage cards, summary
    Exercise1.tsx      speaking drill (mic -> STT -> confidence-weighted review)
    Exercise3.tsx      spelling (typed / drawn / photographed) + phoneme sorting
    Exercise5.tsx      generated story + comprehension questions
    Dashboard.tsx      progress, word list, guardian settings, admin tools
    ui.tsx             Card, Banner, Select, Toggle, ProgressBar, Confetti, SoundButton
```

## Design language

A physical, pressable look: buttons carry a thick color slab underneath and
push down when pressed; cards are 2px borders with generous radii; the primary
accent is violet, with green reserved for "correct" and red for "try again".
`--font-ui` is Nunito; `--font-dys` is Lexend and is used for anything a learner
reads at length.

Motion rules:

- Transform/opacity only, short durations, and `cubic-bezier(0.22, 1, 0.36, 1)`
  or spring-ish curves for entrances.
- A blanket `prefers-reduced-motion` rule disables animation globally.
- Confetti and other celebrations respect the guardian toggle
  (`src/celebrations.ts`).

## State and data

There is no global store. `App.tsx` owns the learner id (persisted under
`mbdt.learnerId`), the dashboard snapshot and today's status. Exercises fetch
their own rounds and never cache answers client-side: the word for a spelling
task is only available as audio.
