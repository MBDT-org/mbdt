# Custom word sets

Drop a `.json` file here to add your own word set. It appears in
**Guardian → Word set** after the backend restarts, and can then be selected
for any learner.

Copy `my-set.example.json`, rename it (the file name is used as the id if you
omit `id`), and edit the words. Files ending in `.json` are loaded; `.example.json`
is ignored.

```json
{
  "id": "week-3-spelling",
  "label": "Week 3 spelling — short a",
  "words": [
    { "word": "cat", "phoneme": "short-a" },
    { "word": "hat", "phoneme": "short-a" },
    "mat"
  ]
}
```

- **id** — unique, lowercase, no spaces. It is the key stored in the database.
- **label** — what guardians see in the dropdown.
- **words** — strings, or objects with a `word` and an optional `phoneme`.
  The phoneme is used by the "Sort by sound" stage; plain strings are grouped
  under `misc` there and work fine everywhere else.
- Words are lowercased and de-duplicated per learner automatically. If a learner
  already has a word, it is kept with its existing history.
- Set `"override": true` to replace a built-in set with the same id (not
  recommended: existing learner history keeps its old rows).
