# Built-in word data

Everything the app ships is meant to be redistributable. Before adding a list,
check that its licence allows redistribution, and record the source below.

| Set | Source | Licence |
|---|---|---|
| `phonics-starter`, `phonics-growing` | Written for MBDT | MIT |
| `dolch-pre-primer`, `dolch-grade-1`, `dolch-grade-2` | Dolch sight-word lists | Public domain |
| `fry-101-200` | Fry 1000 Instant Words | Public domain |
| `uk-year-1-2`, `uk-year-3-4` | English national curriculum statutory spelling lists | Crown copyright, [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| `letters-sounds-phase-5` | *Letters and Sounds* (UK DfE) | Crown copyright, Open Government Licence v3.0 |
| `homophones` | Written for MBDT | MIT |
| `awl` | [Academic Word List](https://www.wgtn.ac.nz/lals/resources/academicwordlist), Averil Coxhead | Free to use with attribution |
| `ngsl` | [New General Service List](https://newgeneralservicelist.com/), Browne, Culligan & Phillips (2013) | CC BY-SA 4.0 |

Word lists are facts, but a published, curated list can still carry terms of use.
Oxford 3000/5000, Cambridge Flyers/PET, the Hong Kong EDB lists and the HKEAA
glossary are **not** bundled for that reason, even though they are useful.

## Adding a list you have the right to use

You do not need to edit code. Paste your list into a JSON file in
`backend/data/word_sets/`:

```json
{
  "id": "week-3-spelling",
  "label": "Week 3 spelling (short a)",
  "words": [
    { "word": "cat", "phoneme": "short-a" },
    { "word": "hat", "phoneme": "short-a" },
    "mat"
  ]
}
```

Plain strings work too. A `phoneme` label groups the word in the "Sort by
sound" activity; unlabelled words are grouped under `misc`. See
[`word_sets/README.md`](word_sets/README.md) for the full shape.

That folder is git-ignored except for the shipped example, so a personal or
classroom list does not end up in a commit by accident. Do not commit a list
whose licence does not allow it.
