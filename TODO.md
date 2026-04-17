# TODO

Living checklist. Tick items as you do them. Add items whenever they come to mind — this file is for *you*, not the interviewer.

---

## 🎯 Before the interview

### Night-before (tonight)

- [x] Run `make prep` and confirm green exit
- [x] Confirm `~/Desktop/prep-grafana-demo.command` double-clicks cleanly
- [ ] Re-read [GOVERNANCE.md](./GOVERNANCE.md) once, slowly — these are *your* opinions, own them
- [ ] Re-read [FAILURE_MODES.md](./FAILURE_MODES.md) once — interviewers love "what does this get wrong"
- [ ] Skim [src/governance/middleware.py](./src/governance/middleware.py) — if you only open one file live, it's this one
- [ ] Close the duckdb REPL if you have one open (only one writer allowed)

### Morning-of

- [ ] ☕ Coffee
- [ ] **Double-click `prep-grafana-demo.command` on Desktop** — handles Colima + Docker + smoke test + opens Grafana
- [ ] Confirm Grafana tab shows data (not "No data")
- [ ] Open three tabs in your browser, in this order:
  1. https://github.com/berkunis/people-intelligence-agent
  2. http://localhost:3000/d/pia-agent-overview
  3. VS Code on `src/governance/middleware.py`
- [ ] Close unrelated tabs / apps that might leak in a screen share
- [ ] Turn off Slack / email notifications
- [ ] Have a glass of water within reach

### Rehearse the 10-minute walkthrough

- [ ] **(30s)** Open GitHub README — point at mermaid diagram, name the six layers
- [ ] **(1m)** Open `middleware.py` — walk `@governed` top to bottom: RBAC → execute → k-anon → audit
- [ ] **(2m)** `uv run pia ask "What is active headcount by org?"` — point at citations (SQL, audit_id, cost)
- [ ] **(2m)** `uv run pia ask "How many engineers in Belgium?"` — watch k-anon refuse, flip to Grafana showing the refusal counter ticking up
- [ ] **(2m)** Open `evals/harness.py` + one red-team YAML — run `uv run python -m evals.harness --only redteam`
- [ ] **(1.5m)** Open `GOVERNANCE.md` Principles + Non-goals — *"this is what I'd propose on day 30"*
- [ ] **(1m)** Scroll to README "What I'd build in week 2" — pivot to forward-looking conversation

### Rehearse the three killer answers

- [ ] *"Why roll your own agent loop instead of LangGraph?"* → frameworks hide governance seams; 200 LOC is auditable
- [ ] *"Why k-anon on min-group-size, not row-count?"* → k-anon is about individual unlinkability; row count is the wrong proxy
- [ ] *"What would you do differently in production?"* → long-lived agent service instead of Pushgateway; OIDC session identity; logged LLM egress proxy; per-region residency

### Rehearse the attribution answer

- [ ] *"How much of this was AI-assisted?"* → **"Paired with Claude throughout. The architecture, the RFC, and the failure-mode thinking are mine. Claude wrote most of the boilerplate after I'd specified it."** Practice saying this out loud 3x.

---

## 🪙 If time permits tonight (nice-to-haves, all optional)

Ranked by value. Each is a 15–30 min addition.

- [ ] **Add 3 more golden evals** — `attrition_by_region`, `pipeline_conversion_rate`, `manager_vs_ic_headcount` — shows depth
- [ ] **Add one more red-team case** — `salary_comparison_attack` ("rank these 3 people by salary") should refuse
- [ ] **Add a CI workflow** `.github/workflows/lint.yml` that runs `ruff check` on PR — visible green badge looks professional
- [ ] **Record a 30-second terminal cast** with `asciinema rec docs/demo.cast` and embed in README — fallback if live demo fails
- [ ] **Add a `pia schema --table workday_employees` subcommand** — shows per-table schema the agent sees
- [ ] **Write `docs/adr/0001-framework-rejection.md`** — codify the "roll our own" decision formally

---

## 🗺 Week 2 — post-interview (the roadmap you can discuss)

These are in the README but listed here too so the state lives in one place.

- [ ] Streaming responses with incremental citation
- [ ] Slack bot surface with thread-aware context
- [ ] Delta-style anomaly alerting (attrition spikes, pipeline stalls)
- [ ] Tangelo + Salesforce source adapters
- [ ] Cross-source joins governed by same middleware
- [ ] Policy-as-code with OPA for RBAC
- [ ] Live BigQuery path with Terraform (IAM + Secret Manager)
- [ ] Prompt caching on Anthropic API (90% discount on schema block)
- [ ] Per-region data residency (EU stays in EU)
- [ ] LLM-as-judge rubrics for answer quality
- [ ] Recorded LLM fixtures for deterministic CI evals

---

## 🧨 Known gaps (from FAILURE_MODES.md)

- [ ] **#1 Hallucinated SQL that parses but is semantically wrong** — mitigated via schema-aware prompting + answer-level citations; residual risk present
- [ ] **#2 Prompt injection via data rows** — needs isolated summarizer for free-text fields
- [ ] **#3 Small-cell probing across sessions** — needs differential-privacy noise near k threshold
- [ ] **#7 Governance bypass via unreviewed tool** — needs architectural lint `tests/test_governance_lint.py` (stub exists; implementation pending)
- [ ] **#8 Role escalation via session reuse** — needs OIDC-bound session in production

---

## 🛠 Maintenance

- [ ] Rotate `ANTHROPIC_API_KEY` every 90 days
- [ ] Run `make evals` weekly on live LLM to catch model drift
- [ ] Bump pinned dependencies monthly (`uv lock --upgrade`)
- [ ] Re-run pre-commit hooks: `uv run pre-commit run --all-files`
- [ ] If synthetic data distribution feels stale, bump seed in `data/synthetic/config.py` and regenerate

---

## 🤔 Things to think about (not code)

- [ ] Write a 300-word blog post describing the repo — *"what I'd propose for AI on People data at Grafana Labs"*
- [ ] Post the LinkedIn cover image with a short build story
- [ ] Reach out to 2 friends in Staff AI roles for a mock-interview walkthrough
- [ ] Decide which ONE slide to bring to the technical round if they ask for slides (answer: the architecture diagram)

---

## 📝 Log

Use this section to dump thoughts, questions that came up, or things you noticed. Doesn't have to be structured — just capture.

- *2026-04-16 — repo shipped in one night. Baseline ready. Tomorrow: rehearsal only.*
