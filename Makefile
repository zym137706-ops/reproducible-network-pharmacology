.PHONY: install test lint format validate ingest quickstart demo clean

install:
	uv sync --locked --extra dev

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

validate:
	uv run rnp validate --config examples/quickstart/run.yaml

ingest:
	uv run rnp ingest stp --config examples/quickstart/run.yaml --run-id quickstart

quickstart:
	uv run rnp validate --config examples/quickstart/run.yaml
	uv run rnp ingest stp --config examples/quickstart/run.yaml --run-id quickstart
	uv run rnp intersect --config examples/quickstart/run.yaml --targets results/quickstart/targets.tsv
	uv run rnp network --config examples/quickstart/run.yaml --intersect results/quickstart/intersect
	uv run rnp enrich --config examples/quickstart/run.yaml --intersect results/quickstart/intersect
	uv run rnp report --config examples/quickstart/run.yaml --run-dir results/quickstart
	uv run rnp manifest --run-dir results/quickstart --check-inputs

demo:
	uv run python scripts/synthetic_demo.py --out .demo

clean:
	rm -rf results .demo tests/fixtures/run/_out .pytest_cache .ruff_cache
