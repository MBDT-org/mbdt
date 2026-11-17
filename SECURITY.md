# Security policy

MBDT is a local-first desktop application. It is designed to run on one computer,
listening on `127.0.0.1`, and it has no learner authentication. Do not expose the
backend port (`8777` by default) to a network or the internet.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private
vulnerability reporting:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Include the affected version or commit, steps to reproduce, and the impact you
   expect.

If private reporting is not available, contact a maintainer listed in the repository
profile. We aim to acknowledge reports within a week.

## In scope

- Leakage of `backend/.env`, the gateway API key (Requesty or OpenRouter), or admin credentials.
- Prompt or input handling that sends learner data off-device beyond what
  [README → Privacy and data](README.md#privacy-and-data) describes.
- SQL injection, path traversal, or arbitrary file access through the HTTP API.
- Story or OCR output that bypasses the guardian's safety filters in a way a
  supervising adult would not expect.
- Cross-site scripting in the frontend or the landing page.

## Out of scope

- The weaker parts of the local trust model that the documentation already states:
  no learner authentication, a simple admin gate for shared devices, and the
  unsalted SHA-256 admin password hash.
- Denial of service from a local process the user already runs.
- Provider-side behaviour of the selected gateway or the model vendors. Report those to the
  provider.

## Handling data

Never include a learner's name, recordings, review history, API keys, or a copy of
`backend/mbdt.db` in a report. A minimal synthetic reproduction is enough.
