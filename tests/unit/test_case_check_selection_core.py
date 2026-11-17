"""The selection recheck against what the real stages write (not hand-made files).

The compounds stage, the selection stage, `ingest stp --selection` and `intersect` run as the real
code (with the fake structure describer of the other tests: no RDKit needed); the recheck must find
nothing wrong in what they wrote, and must notice a run that did not use the selection.
"""

from __future__ import annotations

from pathlib import Path

from case_check_support import load_check
from selection_ingest_support import FOUR_OK, decision, downstream, ingest, make

LABEL = "0.10"
ROWS = [
    decision("Compound 1", "include"),
    decision("Compound 2", "include", reason="ok;fine", refs="notes.pdf"),
    decision("Compound 3", "exclude", reason="out_of_scope"),
    decision("Compound 4", "exclude", reason="too_polar;out_of_scope"),
]


def recheck(case, run_dir: Path):
    table = case.root / "inputs" / "compounds.tsv"
    return load_check().check_selection(
        table,
        case.decisions,
        {LABEL: case.compounds},
        {LABEL: case.selection},
        {LABEL: run_dir},
    )


def test_the_recheck_finds_nothing_wrong_in_what_the_real_stages_wrote(tmp_path) -> None:
    case = make(tmp_path, ROWS, FOUR_OK)
    run_dir = Path(ingest(case)["run_dir"])
    downstream(case, run_dir)
    record = recheck(case, run_dir)
    assert record["status_counts"] == {"excluded": 2, "selected": 2}
    assert record["rows"] == 4


def test_the_recheck_follows_the_groups_of_the_real_stages(tmp_path) -> None:
    rows = [
        decision("Compound 1", "include", group="g1"),
        decision("Compound 2", "include", group="g1"),
        decision("Compound 3", "exclude", group="g2", reason="out_of_scope"),
        decision("Compound 4", "exclude", group="g2", reason="out_of_scope"),
    ]
    case = make(tmp_path, rows, FOUR_OK, groups=["g1", "g1", "g2", "g2"])
    run_dir = Path(ingest(case)["run_dir"])
    downstream(case, run_dir)
    assert recheck(case, run_dir)["status_counts"] == {"excluded": 2, "selected": 2}


def test_the_recheck_notices_a_run_that_did_not_use_the_selection(tmp_path) -> None:
    import pytest

    case = make(tmp_path, ROWS, FOUR_OK)
    run_dir = Path(ingest(case, selection=None)["run_dir"])
    downstream(case, run_dir)
    with pytest.raises(AssertionError) as raised:
        recheck(case, run_dir)
    lines = str(raised.value).splitlines()
    assert f"{LABEL}: compounds_registered.tsv: selection_status: the column is missing" in lines
    assert any(
        line.startswith(f"{LABEL}: stp_audit.json: schema_version: expected '1.2'")
        for line in lines
    )
    assert any("is not a selected compound" in line for line in lines)
