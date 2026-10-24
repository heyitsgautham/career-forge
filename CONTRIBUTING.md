# Contributing to CareerForge

Thanks for helping out.
This file covers the local setup, the checks CI runs, and how changes should land.

## Set up

Follow the Install section of the [README](README.md).
You need Python 3.11 with uv for the backend and Node.js 22.12 or newer for the frontend.
Neither the test suites nor a local run need an AWS account.

## Before you open a pull request

Run the same checks CI runs.

Backend, from `project/backend`:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest --cov
```

Frontend, from `project/frontend`:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

A pull request needs every CI job green before it merges.

## How changes should land

Keep each commit to one change, and put the tests that prove a behavior change in the same commit.
Formatting-only and refactor-only changes go in their own commits, separate from features and fixes.

Commit subjects follow `type(scope): subject` in the imperative mood, for example `fix(resumes): return the PDF from download_pdf`.
The types in use are `feat`, `fix`, `refactor`, `test`, `docs`, `build`, `ci`, `style` and `chore`.

## Tests

Backend tests live in `project/backend/tests/` and run against a throwaway SQLite database.
Stub Bedrock, embeddings and other AWS clients with `monkeypatch`, and never let a test reach the network.
Frontend tests sit next to the code in `__tests__/` folders and run in jsdom with Testing Library.

Use synthetic people, emails and companies in fixtures, such as `asha@example.com` or `Sample Labs`.
Never copy a real profile, resume or token into a test.

## Dependencies

Add backend packages with `uv add <package>`, which updates `pyproject.toml` and `uv.lock`.
Then export the pip file with `uv export --no-dev --no-hashes -o requirements.txt` and commit all three.
Add frontend packages with `npm install --save-exact <package>` and commit `package-lock.json`.
Dependabot opens weekly update pull requests for both.

## Secrets

Never commit `.env` files, keys or tokens.
Add any new setting to the matching `.env.example` with a placeholder value.
CI runs gitleaks on every push and fails if it finds a secret.
