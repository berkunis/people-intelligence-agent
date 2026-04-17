# Contributing

This repo is a reference implementation and a portfolio artifact. External PRs are welcome but not the primary goal; the guides below exist so that extending the system is obvious, not obscure.

## Dev setup

```bash
uv sync --all-extras
pre-commit install
make seed
make dbt-run
make test
```

## Adding a new source (e.g., Salesforce)

The Workday / Greenhouse / Docebo adapters are the template. To add Salesforce:

1. **Schema.** Add a Faker generator in `data/synthetic/salesforce.py` producing the tables you want to expose (e.g., `opportunities`, `accounts`, `contacts`). Use the same seed discipline — fixed seed, no external data.

2. **Raw load.** Add a loader in `src/storage/load_raw.py` that writes the Faker output to `raw_salesforce_*` tables in the warehouse.

3. **dbt marts.** Create `dbt/models/staging/stg_salesforce_*.sql` and `dbt/models/marts/salesforce/*.sql`. Mirror the Workday structure: staging for column cleanup, marts as the agent's interface.

4. **Governance.** Map Salesforce fields to governance classes in `src/governance/pii.py` — which columns are PII, which are role-restricted, which require k-anonymity aggregation.

5. **Tools.** Add or extend tools in `src/agent/tools.py`. New tools must:
   - Declare their required `requester_role` grants
   - Be wrapped in `@governed` (enforced by architectural lint)
   - Have a schema-aware docstring for the LLM

6. **Evals.** Add ≥5 golden Q&A pairs in `evals/golden/salesforce/`. Add ≥3 red-team cases in `evals/redteam/salesforce/` (injection, role escalation, small-cell probe).

7. **Docs.** Update `GOVERNANCE.md` with any new data classes. Add an ADR if you're making a non-obvious design choice.

## Code style

- Type hints required (enforced by `mypy --strict`)
- Ruff for linting + formatting
- Functions > classes when state isn't needed
- Docstrings on public APIs; comments only for non-obvious *why*

## Running evals locally

- Fast path: `make evals-offline` — uses recorded fixtures, no API costs
- Real path: `make evals` — calls the live LLM, costs tokens

## Commit hygiene

- One concern per commit
- Pre-commit hooks must pass (gitleaks, detect-secrets, ruff)
- PR description should reference any ADR touched or added
