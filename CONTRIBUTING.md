# Contributing

Thanks for taking a look. This is primarily a personal research-engineering project, but small,
well-scoped contributions are welcome.

## Development setup

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
uv run ruff check .
```

The enrichment bridge additionally needs R 4.3+ with `clusterProfiler`, `org.Hs.eg.db` and
`jsonlite`. Without R, the bridge test is skipped and everything else still runs.

## What a good change looks like

- One behaviour per pull request, with a test for the happy path **and** a failure mode.
- Interfaces first: update the JSON Schema before changing an input or output.
- No data in commits. Fixtures are synthetic and labelled as such.
- No new dependency without a `CHANGELOG.md` entry and a reason in the PR description.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## Reporting a data trap

If you hit a real export that the parser mishandles, open an issue with:

1. the *structure* of the file (header row position, column names), not the science;
2. the exact command and error output;
3. what the tool did versus what you expected.

Do not attach unpublished project data. A fabricated minimal example is better.
