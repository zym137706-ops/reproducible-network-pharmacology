.PHONY: install test lint format validate ingest demo clean

install:
	uv venv
	uv pip install -e ".[dev]"

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

validate:
	uv run rnp validate --config tests/fixtures/run/run.yaml

ingest:
	uv run rnp ingest stp --config tests/fixtures/run/run.yaml

demo:
	uv run python scripts/synthetic_demo.py --out .demo

clean:
	rm -rf results .demo tests/fixtures/run/_out .pytest_cache .ruff_cache
