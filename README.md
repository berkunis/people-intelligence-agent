# people-intelligence-agent

> A governable AI agent over People data — reference implementation for the kind of system I'd propose building on day 30 at a People Technology team.

**Status:** v0.1 — scaffold in progress. Full build tracked in [CHANGELOG.md](./CHANGELOG.md).

---

## The problem

People data lives in five silos (HRIS, ATS, LMS, engagement, comp). Leaders wait days for answers to simple questions — "what's our engineering attrition in EMEA?", "where is the recruiting pipeline slow?" — because pulling them manually crosses team and tool boundaries.

This repo is a reference implementation of a governable AI layer over that data: natural-language questions in, cited answers out, every step observable and every row governed.

## 60-second demo

```bash
make demo
uv run pia ask "What is engineering headcount in EMEA by month, last 12 months?"
```

*(GIF placeholder — will be added when demo is live)*

The agent answers with:
- The SQL it ran
- Row counts and data freshness timestamp
- The prompt version hash used
- A link to the Grafana dashboard showing this query's cost, latency, and governance signals

## How it works

*(Architecture diagram — see `docs/architecture.png`)*

Six layers:
1. **Data** — Faker-synthesized HR data → dbt marts (Workday / Greenhouse / Docebo shapes) in DuckDB or BigQuery
2. **Agent** — typed tool-use loop calling Claude or Gemini via a provider-agnostic abstraction
3. **Governance** — PII anonymization, RBAC, k-anonymity, audit logging, prompt versioning, cost circuit breaker
4. **Evals** — offline-first harness with golden + red-team suites, LLM-as-judge, CI-gated
5. **Observability** — Prometheus metrics + Grafana dashboards, one docker-compose away
6. **Docs** — GOVERNANCE.md RFC, ADRs, FAILURE_MODES.md — how this system is run, not just built

## What makes it safe

- No individual-identifying queries below k=5 rows (configurable)
- PII stripped before any data reaches the LLM
- Role-based tool access (HRBP / Recruiter / Leader / Analyst)
- Every prompt, tool call, and response written to an audit table
- Red-team eval suite for prompt injection, PII exfiltration, role escalation

See [GOVERNANCE.md](./GOVERNANCE.md) for the full RFC.

## How it's measured

| Metric | Current |
|---|---|
| Golden eval pass rate | *(CI badge)* |
| Red-team refusal rate | *(CI badge)* |
| p95 agent latency | *(Grafana)* |
| Avg cost per query | *(Grafana)* |

## Where to look first

Read [TOUR.md](./TOUR.md) for a numbered walkthrough of the 7 files that tell the story.

## What I'd build in week 2

- Streaming responses with incremental citation
- Slack bot surface with thread-aware context
- Delta-style anomaly alerting (attrition spikes, pipeline stalls) pushed to People leaders
- Tangelo + Salesforce source adapters
- Cross-source joins governed by same middleware
- Policy-as-code with OPA for the RBAC layer

## License

MIT — see [LICENSE](./LICENSE).
