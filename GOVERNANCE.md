# Governance: AI over People Data

> **Status:** RFC — v0.1 draft
> **Scope:** how an AI agent should operate on employee data in a People Technology team
> **Audience:** People Ops leaders, Security, Privacy, Data Engineering, peer AI engineers

---

## Principles

1. **People data is sensitive by default.** Every datum is assumed to be PII or employment-related until proven otherwise. The burden of proof is on the system requesting access, not on the human protecting the data.
2. **The model sees as little as possible.** LLMs are assumed to leak: via logs, via fine-tuning, via retrieval. Anonymization happens *before* the model call, not after.
3. **Every answer is attributable.** Provenance (SQL, row count, freshness, prompt hash) is part of the response contract. No floating assertions.
4. **Refusal is a feature.** The system should refuse more than it guesses. k-anonymity, role-based access, and small-cell suppression are first-class, not afterthoughts.
5. **If it's not evaluated, it doesn't ship.** Behavior changes — prompt, model, schema — require a passing eval run.
6. **Observable or off.** Every tool call, every refusal, every dollar spent is measurable in Grafana. If we can't see it, we turn it off.

---

## Data handling

### Anonymization

Before any row reaches the LLM:
- Names → stable internal IDs (`emp_a1b2c3`)
- Emails → domain only (`@company.com`)
- Salaries → bands (`$120–140k`)
- Birthdates, addresses, phone numbers → stripped
- Free-text review comments → summarized by a separate, locally-hosted model with no external network access (future work)

Anonymization is enforced at the storage adapter layer, not the application layer, so a bug in application code cannot leak data.

### Access

Four requester roles with scoped tool access:
- **HRBP** — individual-level for their supported orgs; cross-org aggregates
- **Recruiter** — pipeline-level; no comp data
- **Leader** — their reporting tree only; comp bands, not amounts
- **Analyst** — aggregates only, k≥5

Role is asserted at the session level and checked at every tool call. No tool can be invoked without a matching role grant.

### Small-cell suppression (k-anonymity)

Any aggregate whose result set has fewer than **k=5** rows is refused. Refusal is structured:

```json
{
  "refused": true,
  "reason": "k_anonymity",
  "detail": "Query would return 3 rows; k=5 threshold enforced.",
  "audit_id": "..."
}
```

k is configurable per role and per tool. The agent never rephrases a refused query in an attempt to circumvent.

### Audit

Every agent call writes to `audit.agent_calls`:
- `requester_role`
- `prompt_hash` (references `prompts/` versioned file)
- `tool_calls[]` with arguments + row counts
- `sql_executed[]`
- `refusals[]` with reasons
- `tokens_in`, `tokens_out`, `cost_usd`
- `latency_ms`
- `response_summary` (not the full response; full response stored separately with shorter TTL)

Audit log retention: 365 days. Response content retention: 30 days.

---

## Model governance

### Prompt versioning

Prompts live in `prompts/` as versioned markdown files (`text_to_sql/v1.2.0.md`). Each agent call records the SHA-256 of the prompt used. Rolling back a prompt is a git revert, not a DB update.

### Model selection

- **Default:** Claude (quality on agentic tool use)
- **Alternate:** Gemini (GCP-native; for workloads constrained to Google Cloud's data perimeter)
- Model choice is a deploy-time config, not a runtime decision. No per-request model routing in v1.

### Evaluation gates

No prompt, model, or schema change ships without:
- Golden eval pass rate ≥ 90%
- Red-team refusal rate ≥ 95%
- No regression vs. the prior version on any individual test

Evals run offline against recorded LLM fixtures in CI (fast, free, deterministic). A nightly job runs the real LLM and flags drift.

### Cost governance

Per-request limits:
- Token budget: 50,000 input + output (configurable)
- Tool-call depth: 8 iterations max
- BigQuery bytes scanned: 1 GiB max

Exceeding any limit halts the run with a structured error. Limits are exported as Prometheus metrics; dashboards alert on sustained breach.

---

## Security

- API keys via Secret Manager (GCP) or environment only; never committed
- Service accounts with least-privilege IAM; no `roles/bigquery.admin` in the agent's identity
- All outbound LLM traffic goes through a logged proxy (future work) to enable post-hoc review
- PR builds from forks do not receive repo secrets

---

## Non-goals (explicit)

1. **Individual-level employee rankings, comparisons, or performance predictions.** The agent will refuse; this is a policy, not an oversight.
2. **Free-text answers about identified individuals.** Only HRBP role may retrieve individual-level rows, and only for their supported orgs.
3. **Autonomous action on People systems.** v1 is read-only. Writes to Workday, Greenhouse, etc. are out of scope and require a separate RFC.

---

## Open questions

- How to handle regional data residency (EU employees' data staying in EU)? Likely via per-region dataset + per-region agent deploy. Out of scope for v0.1.
- How to integrate with existing People Analytics workforce metrics? Partner question — align on shared semantic layer rather than reimplement.
- How to surface governance posture to non-technical People leaders? A "governance health" panel in Grafana, designed with a People partner.

---

## Changelog

- **v0.1 (this doc)** — initial draft. No external review yet.
