# Contributing

Thanks for taking a look. This is primarily a personal research-engineering project, but small,
well-scoped contributions are welcome.

## Development setup

```bash
uv sync --locked --extra dev
# Linux/macOS: restore the locked R 4.5.2 / renv library; use the absolute path it prints.
bash scripts/restore_r.sh /abs/path/to/rlib
export R_LIBS=/abs/path/to/rlib

uv run pytest -q
uv run ruff check .
```

Windows PowerShell equivalent:

```powershell
uv sync --locked --extra dev
.\scripts\restore_r.ps1 -Library C:\abs\path\to\rlib
$env:R_LIBS = "C:\abs\path\to\rlib"
uv run pytest -q
uv run ruff check .
```

The verified case environment is **R 4.5.2 with the `renv.lock` library**, restored by the project
`restore_r` script (Linux is the verified CI platform; Windows native R still has the documented
`0xC0000005` limitation). `Rscript` must be discoverable or set via `RNP_RSCRIPT`.

Without a restored R/`Rscript`, only the Rscript-dependent bridge/enrichment tests are skipped
(`pytest.mark.skipif(Rscript not available)`); the remaining Python tests and lint still run. Skipped
tests are not evidence that the R bridge passed—run the Linux CI or restore R to exercise them.

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
