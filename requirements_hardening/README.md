# Agentic Requirements Hardening System (ARHS)

A separate, deterministic-core + role-based-agent system that turns an
architecture-style requirement export into an **L2-oriented, reviewable
requirements baseline** with acceptance criteria, verification methods, trace
links, test design and a human review packet.

It does **not** modify the original input and does **not** claim certification.

## Run

```bash
python -m requirements_hardening.cli run --input inputs/requirements/aeb/aeb_requirements.csv --set aeb
python -m requirements_hardening.cli run --input inputs/requirements/samples/bms_requirements.csv --set bms
python -m requirements_hardening.cli run --input inputs/requirements/samples/eps_requirements.csv --set eps
python -m requirements_hardening.cli run --input inputs/requirements/samples/Motcontrolcomp.csv --set foc
```

Outputs:

- `outputs/req_hardening/<timestamp>_<set>/` — findings, review, metrics, trace, test design, reports.
- `inputs/requirements_hardened/<set>/` — hardened CSV, extended JSON/CSV, test design, trace, polished Markdown.

Each set has its own `data/<set>_overrides.json`, `data/<set>_splits.json`
(optional), `data/<set>_new_requirements.json` and `data/<set>_config.json`.
Sets without a curated split map use the automatic atomic splitter.

## Agents and roles

| Role | What it does |
|---|---|
| Intake/Normalizer | Parse the export, map columns, preserve provenance. |
| Critic | Deterministic rule audit (atomicity, ambiguity, verifiability, trace, interface/timing/safety completeness). |
| Author | Produce hardened fields, acceptance criteria, trace, open issues, gap requirements. |
| Reviewer | Independent deterministic review; accept/revise/reject with comments. |
| Exporter/Reporter | Write the baseline, test design, trace matrix, run report and review packet. |

The Author and Reviewer are separate code paths. In this MVP they are
deterministic; an LLM adapter can be added behind the same JSON contracts
without changing the gate logic.

## Standards profiles

`rules/standards_profiles.json` scopes generic, automotive, aerospace, medical,
rail, machinery and AI/ML profiles. The AEB pilot activates `generic` +
`automotive`. Nothing implies certification.

## Guarantees

- Original input is read-only and hash-checked by tests.
- Every run is versioned under `outputs/req_hardening/`.
- Human approval is required before a baseline is treated as approved.
- Open issues are explicit; the system does not invent safety goals or standards values.

## Tests

```bash
python -m unittest discover -s requirements_hardening/tests -v
```
