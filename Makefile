.PHONY: help install demo seed dbt-run evals evals-offline evals-nightly dashboards tf-plan lint typecheck test clean prep

help:
	@echo "people-intelligence-agent — make targets"
	@echo ""
	@echo "  prep            ★ RUN BEFORE INTERVIEW ★ starts stack + smoke-tests agent + opens Grafana"
	@echo "  install         Install deps via uv (creates .venv)"
	@echo "  seed            Generate synthetic data + load into DuckDB"
	@echo "  dbt-run         Run dbt transformations"
	@echo "  demo            Full stack: seed + dbt + agent + Grafana via docker-compose"
	@echo "  evals-offline   Run eval harness against recorded LLM fixtures (fast, free)"
	@echo "  evals           Run eval harness against live LLM (costs tokens)"
	@echo "  dashboards      Open Grafana in browser"
	@echo "  tf-plan         Terraform plan (no apply)"
	@echo "  lint            Ruff check + format"
	@echo "  typecheck       mypy strict on src/"
	@echo "  test            pytest"
	@echo "  clean           Remove build artifacts + warehouse"

prep:
	@bash bin/prep-demo.sh

install:
	uv sync --all-extras

seed:
	uv run python -m data.synthetic.generate
	uv run python -m storage.load_raw

dbt-run:
	cd dbt && uv run dbt run --profiles-dir .

demo: install seed dbt-run
	docker compose -f infra/docker-compose.yml up -d
	@echo ""
	@echo "Agent: http://localhost:8000"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo ""
	@echo "Try: uv run pia ask 'What is engineering headcount in EMEA?'"

evals-offline:
	uv run python -m evals.harness --mode=offline

evals:
	uv run python -m evals.harness --mode=live

dashboards:
	open http://localhost:3000

tf-plan:
	cd infra/terraform && terraform init -backend=false && terraform validate && terraform plan

lint:
	uv run ruff check src tests evals
	uv run ruff format --check src tests evals

typecheck:
	uv run mypy src

test:
	uv run pytest tests -v

clean:
	rm -rf data/warehouse/*.duckdb data/synthetic/*.parquet dbt/target dbt/logs
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
