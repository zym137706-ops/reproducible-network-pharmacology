"""`rnp report` after `ingest stp --selection`: one line with the counts of the decisions.

When `compounds_registered.tsv` has the column `selection_status`, the report says how many
compounds are selected, excluded, and held for review or quarantined, right after the line with the
number of registered compounds. Without the column the report is what it was. Selecting everything
changes the report by that one line only.
"""

from __future__ import annotations

import re
from pathlib import Path

from selection_ingest_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    FOUR_OK,
    decision,
    downstream,
    ingest,
    make,
)

TWO_GROUPS = ["g1", "g1", "g2", "g2"]
ALL_INCLUDED = [
    decision(f"Compound {n}", "include", group=group) for n, group in enumerate(TWO_GROUPS, start=1)
]


# --- the report -----------------------------------------------------------------------------------
def report_lines(text):
    return text.splitlines()


def test_the_report_counts_the_decisions(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case)["run_dir"])
    lines = report_lines(downstream(case, run_dir)["report"])
    at = lines.index("- Compounds registered: 4")
    assert (
        lines[at + 1]
        == "- Compound selection: 2 selected, 2 excluded, 0 needs review or quarantined"
    )
    assert lines[at + 2] == "- STP exports: bound 2, quarantined 0, missing 0"


def test_the_report_counts_the_compounds_held_for_review_and_the_quarantined_ones(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    run_dir = Path(ingest(case)["run_dir"])
    lines = report_lines(downstream(case, run_dir, allow_partial=True)["report"])
    at = lines.index("- Compounds registered: 4")
    assert (
        lines[at + 1]
        == "- Compound selection: 1 selected, 1 excluded, 2 needs review or quarantined"
    )
    assert lines[at + 2] == "- STP exports: bound 1, quarantined 1, missing 0"


def test_the_report_without_a_selection_has_no_such_line(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case, selection=None)["run_dir"])
    text = downstream(case, run_dir, allow_partial=True)["report"]
    assert "selection" not in text.lower()
    lines = report_lines(text)
    at = lines.index("- Compounds registered: 4")
    assert lines[at + 1] == "- STP exports: bound 2, quarantined 2, missing 0"


def normalised(text, run_id):
    """The report without the name of its run directory and without hashes (audits differ)."""
    return re.sub(r"[0-9a-f]{64}", "<sha256>", text.replace(run_id, "RUN")).splitlines()


def test_the_report_of_everything_selected_differs_by_one_line_only(tmp_path):
    case = make(tmp_path, ALL_INCLUDED, FOUR_OK, groups=TWO_GROUPS)
    plain = Path(ingest(case, run_id="run_plain", selection=None)["run_dir"])
    chosen = Path(ingest(case, run_id="run_chosen")["run_dir"])
    left = normalised(downstream(case, plain)["report"], "run_plain")
    right = normalised(downstream(case, chosen)["report"], "run_chosen")
    extra = "- Compound selection: 4 selected, 0 excluded, 0 needs review or quarantined"
    assert extra in right
    assert [line for line in right if line != extra] == left
