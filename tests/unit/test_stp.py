"""STP parsing: status taxonomy, counts and known traps."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnp.errors import InputError
from rnp.io import stp

HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)


def _write(tmp_path: Path, body: str, name: str = "export.csv") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_csv_ok(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "valid.csv", threshold=0.10)
    assert (result.rows_total, result.rows_valid, result.rows_invalid) == (5, 5, 0)
    assert (result.rows_below_threshold, result.rows_used) == (1, 4)
    assert result.status == "ok"
    assert result.records[0]["probability"] == pytest.approx(0.4231)


def test_xlsx_merged_title_row(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "merged_title.xlsx", threshold=0.10)
    assert result.fmt == "xlsx"
    assert result.header_row_index == 1
    assert (result.rows_total, result.rows_used) == (3, 2)
    assert {record["common_name"] for record in result.records} == {"CA2", "TNF"}


def test_multi_symbol_is_flagged_not_split(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "multi_symbol.csv", threshold=0.10)
    assert result.rows_used == 2
    assert [w["code"] for w in result.warnings].count("multi_symbol_common_name") == 2
    assert all(record["multi_symbol_common_name"] for record in result.records)


def test_composite_target_kept_as_one_row(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "complex_target.csv", threshold=0.10)
    assert result.rows_used == 2
    assert len({record["target"] for record in result.records}) == 2
    assert all(record["is_complex"] for record in result.records)
    assert [w["code"] for w in result.warnings].count("complex_target") == 2


def test_invalid_rows_are_not_counted_as_below_threshold(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "bad_probability.csv", threshold=0.10)
    assert result.rows_total == 5
    assert result.rows_valid == 2
    assert result.rows_invalid == 3
    assert result.rows_below_threshold == 0
    assert result.rows_used == 2
    assert result.status == "partial"
    assert {error["code"] for error in result.errors} == {"invalid_probability"}


def test_all_below_threshold_is_its_own_status(tmp_path: Path) -> None:
    path = _write(tmp_path, "A,CA2,P00918,,X,0.04,No\nB,ESR1,P03372,,X,0.02,No\n")
    result = stp.parse_export(path, threshold=0.10)
    assert result.status == "below_threshold"
    assert (result.rows_valid, result.rows_below_threshold, result.rows_used) == (2, 2, 0)


def test_all_invalid_is_its_own_status(tmp_path: Path) -> None:
    path = _write(tmp_path, "A,CA2,P00918,,X,abc,No\nB,ESR1,P03372,,X,1.4,No\n")
    result = stp.parse_export(path, threshold=0.10)
    assert result.status == "invalid_rows"
    assert (result.rows_valid, result.rows_invalid) == (0, 2)


def test_empty_table_is_no_predictions(fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "empty.csv", threshold=0.10)
    assert result.status == "no_predictions"
    assert result.empty_table is True
    assert result.rows_total == 0


def test_comma_decimal_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'A,CA2,P00918,,X,"0,27",No\n')
    assert stp.parse_export(path, threshold=0.10).rows_used == 1


def test_missing_header_raises_with_seen_columns(fixtures: Path) -> None:
    with pytest.raises(InputError) as excinfo:
        stp.parse_export(fixtures / "stp" / "missing_header.csv", threshold=0.10)
    assert "header not found" in excinfo.value.message


def test_missing_required_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "no_probability.csv"
    path.write_text(
        "Target,Common name,Uniprot ID,Target Class\nA,CA2,P00918,X\n", encoding="utf-8"
    )
    with pytest.raises(InputError) as excinfo:
        stp.parse_export(path, threshold=0.10)
    assert "missing required columns" in excinfo.value.render()


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        stp.parse_export(tmp_path / "nope.csv", threshold=0.10)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.25, 0.25),
        ("0.25", 0.25),
        ("0,25", 0.25),
        (" 0.25 ", 0.25),
        (None, None),
        ("", None),
        ("abc", None),
        (1.4, None),
        (-0.1, None),
        (float("nan"), None),
    ],
)
def test_parse_probability(raw, expected) -> None:
    assert stp.parse_probability(raw) == expected


def test_targets_tsv_is_sorted_and_keeps_precision(tmp_path: Path, fixtures: Path) -> None:
    result = stp.parse_export(fixtures / "stp" / "valid.csv", threshold=0.10)
    records = [
        {
            **record,
            "compound_id": "CMP0001",
            "group": "all",
            "submission_id": "S1",
            "source_file": "compound_a.csv",
        }
        for record in result.records
    ]
    out = tmp_path / "targets.tsv"
    stp.write_targets_tsv(records, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("compound_id\tgroup\tsubmission_id\tsource_file")
    probabilities = [float(line.split("\t")[9]) for line in lines[1:]]
    assert probabilities == sorted(probabilities, reverse=True)
