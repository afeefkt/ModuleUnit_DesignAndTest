# Contributing to MUD_MUT

Thanks for your interest! MUD_MUT is a local-AI, ASPICE-aligned pipeline that turns AUTOSAR requirements into
validated Module Unit Design flow charts and CppUTest unit tests. Contributions of all kinds are welcome.

## Repository structure

This is a **monorepo** of two independently-runnable services plus glue:

- `mud-tool/` — the design half (requirements → MUD spec → UML/flow charts → C-skeleton). Python package `mudtool`.
- `cpputest-rag/` — the verification half (C code → RAG → CppUTest → coverage). FastAPI + static frontend.
- `bridge/` — end-to-end glue and requirement→test traceability.

Both halves were imported with full git history via `git subtree`. Keep changes scoped to one half per PR where
possible.

## Development setup

```bash
# Design half
cd mud-tool/python-sidecar
pip install -e ".[dev]"
pytest                       # unit tests
ruff check . && mypy src     # lint + types

# Verification half
cd cpputest-rag
docker compose up            # backend + frontend + ollama + test-runner
```

Use the local backend for development: `cp .env.local.example .env` (no API key needed).

## Guidelines

- **Keep it local-first.** New AI features must work on local 7B models; a cloud/API path is optional, never required.
- **Wrap the model in guardrails.** Prefer adding a validator, reviewer pass, or schema check over trusting raw
  model output. See "How we make 7B models reliable" in the [README](README.md).
- **Never commit secrets.** Only `*.example` env files are tracked. `.env` is git-ignored.
- **Match the surrounding code** — naming, comment density, and idiom of the file you are editing.
- **Add tests** for behavioral changes (`pytest` on the mud-tool side; CppUTest samples on the cpputest-rag side).

## Pull requests

1. Fork and branch from `main` (`feature/…`, `fix/…`).
2. Make the change + tests; run the linters/tests above.
3. Open a PR describing the change and how you verified it.
4. By contributing, you agree your contribution is licensed under the project's [Apache-2.0](LICENSE) license.

## Reporting security issues

Please do **not** open a public issue for security problems (e.g. the Docker-socket exposure noted in the README).
Contact the maintainers privately first.
