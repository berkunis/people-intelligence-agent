# Tour

A 7-stop walkthrough for reviewers. Each stop answers: *why does this matter?*

1. **[GOVERNANCE.md](./GOVERNANCE.md)** — the RFC. Start here. This is how I'd propose running AI on People data, not just how this repo works.
2. **[docs/adr/](./docs/adr/)** — the decisions I made and the ones I rejected. Read `0003-framework-rejection.md` for the clearest signal.
3. **[src/governance/middleware.py](./src/governance/middleware.py)** — PII, RBAC, k-anonymity, audit, all in one pre/post hook around every tool call. The load-bearing file.
4. **[src/agent/loop.py](./src/agent/loop.py)** — typed tool-use state machine. ~200 lines. No framework.
5. **[evals/harness.py](./evals/harness.py)** — offline-first eval runner. Golden + red-team. This is how we prove the system still works tomorrow.
6. **[infra/grafana/dashboards/agent_overview.json](./infra/grafana/dashboards/agent_overview.json)** — the agent monitoring itself. Meta-flex, but also the right answer.
7. **[FAILURE_MODES.md](./FAILURE_MODES.md)** — the honest list of what this system still does wrong, and how I detect it.
