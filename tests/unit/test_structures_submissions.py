"""Reading the submission log and binding it to the registered structures (docs/upstream.md, 8.3).

Nothing here needs RDKit: structures are registered with a fake describer.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
from structures_support import (
    LOG_COLUMNS,
    NOW,
    TOOLKIT_VERSION,
    Describer,
    compound,
    log_row,
    write_export,
    write_log,
    write_text,
)

from rnp.errors import InputError
from rnp.structures import (
    BindingResult,
    LogRow,
    SubmissionOutcome,
    bind_submissions,
    read_submission_log,
    register_structures,
    species_label,
)
from rnp.structures import submissions as submissions_module


def registered(rows):
    return register_structures(
        rows, [], toolkit_version=TOOLKIT_VERSION, now=NOW, describe=Describer()
    )


def entry(number: int, **fields) -> LogRow:
    return LogRow(number, {key: str(value) for key, value in fields.items()})


def one(tmp_path, log_fields=None, smiles="CCO", species="Homo_sapiens", **row_fields):
    """Bind one compound (c1.xlsx exists) to one log row built from `log_fields`."""
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    rows = [compound(1, smiles, **row_fields)]
    registration = registered(rows)
    fields = log_row(1, digest)
    fields.update(log_fields or {})
    log = [LogRow(1, fields)]
    result = bind_submissions(rows, registration.outcomes, log, stp_dir=stp, species=species)
    return result.outcomes[0], digest, result


def issue_view(outcome):
    return [(i.level, i.code, i.source, i.row, i.compound_id) for i in outcome.issues]


def test_a_log_row_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry(1, stp_file="c1.xlsx").row = 99


def test_the_rule_version_and_the_species_label():
    assert submissions_module.RULE_VERSION == "v0.2.0-submission-binding"
    assert species_label("Homo_sapiens") == "Homo sapiens"
    assert species_label("Mus_musculus") == "Mus musculus"


# --- reading the log ------------------------------------------------------------------------------
def test_reading_strips_every_cell_and_numbers_the_data_rows(tmp_path):
    rows = [
        log_row(1, "a" * 64, stp_file="  c1.xlsx ", compound=" Compound 1\t"),
        log_row(2, "b" * 64),
    ]
    path = write_log(tmp_path / "log.tsv", rows)
    entries = read_submission_log(path)
    assert [e.row for e in entries] == [1, 2]
    assert all(isinstance(e, LogRow) for e in entries)
    assert entries[0].cells["stp_file"] == "c1.xlsx"
    assert entries[0].cells["compound"] == "Compound 1"
    assert set(entries[0].cells) == set(LOG_COLUMNS)
    assert entries[1].cells["result_sha256"] == "b" * 64


def test_reading_accepts_a_bom_crlf_and_extra_columns(tmp_path):
    header = "\t".join(["stp_file", "submitted_structure", "species", "submitted_date", "notes"])
    body = "c1.xlsx\tCCO\tHomo sapiens\t2026-10-21\tchecked twice"
    path = tmp_path / "log.tsv"
    path.write_bytes((chr(0xFEFF) + header + "\r\n" + body + "\r\n").encode("utf-8"))
    (only,) = read_submission_log(path)
    assert only.cells["notes"] == "checked twice"
    assert only.cells["species"] == "Homo sapiens"


def test_blank_lines_are_skipped_and_do_not_count(tmp_path):
    header = "stp_file\tsubmitted_structure\tspecies\tsubmitted_date"
    first = "a.xlsx\tCCO\tHomo sapiens\t2026-10-21"
    second = "b.xlsx\tCCN\tHomo sapiens\t2026-10-22"
    path = write_text(tmp_path / "log.tsv", f"{header}\n{first}\n\n\n{second}\n")
    assert [(e.row, e.cells["stp_file"]) for e in read_submission_log(path)] == [
        (1, "a.xlsx"),
        (2, "b.xlsx"),
    ]


def test_a_log_with_only_a_header_has_no_rows(tmp_path):
    path = write_text(
        tmp_path / "log.tsv", "stp_file\tsubmitted_structure\tspecies\tsubmitted_date\n"
    )
    assert read_submission_log(path) == []


def test_a_header_only_log_still_needs_the_required_columns(tmp_path):
    path = write_text(tmp_path / "log.tsv", "stp_file\tspecies\n")
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    assert any("submitted_structure" in d and "submitted_date" in d for d in caught.value.details)


def test_a_missing_log_file_is_an_input_error(tmp_path):
    with pytest.raises(InputError):
        read_submission_log(tmp_path / "nowhere.tsv")


@pytest.mark.parametrize(
    "missing", ["stp_file", "submitted_structure", "species", "submitted_date"]
)
def test_a_required_column_must_be_present(tmp_path, missing):
    columns = [
        c for c in ["stp_file", "submitted_structure", "species", "submitted_date"] if c != missing
    ]
    row = {
        "stp_file": "a.xlsx",
        "submitted_structure": "CCO",
        "species": "Homo sapiens",
        "submitted_date": "2026-10-21",
    }
    path = write_text(
        tmp_path / "log.tsv", "\t".join(columns) + "\n" + "\t".join(row[c] for c in columns) + "\n"
    )
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    assert "log.tsv" in caught.value.message
    assert any(missing in detail for detail in caught.value.details)


@pytest.mark.parametrize(
    "field, value",
    [
        ("species", "human"),
        ("species", "Homo_sapiens"),
        ("submitted_date", "21/10/2026"),
        ("submitted_date", ""),
        ("result_sha256", "A" * 64),
        ("result_sha256", "abc"),
        ("export_kind", "native"),
        ("submitted_structure", "CC O"),
        ("submitted_structure", ""),
        ("stp_file", ""),
        ("pubchem_cid", "abc"),
        ("result_rows", "0"),
    ],
)
def test_an_invalid_value_names_the_row_and_the_column(tmp_path, field, value):
    rows = [log_row(1, "a" * 64), log_row(2, "b" * 64)]
    rows[1][field] = value
    path = write_log(tmp_path / "log.tsv", rows)
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    assert caught.value.exit_code == 2
    assert any(d.startswith("row 2:") and field in d for d in caught.value.details), (
        caught.value.details
    )
    assert not any(d.startswith("row 1:") for d in caught.value.details)


def test_every_invalid_row_is_listed(tmp_path):
    rows = [
        log_row(1, "a" * 64, species="x"),
        log_row(2, "b" * 64),
        log_row(3, "c" * 64, submitted_date="y"),
    ]
    path = write_log(tmp_path / "log.tsv", rows)
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    starts = {detail.split(":")[0] for detail in caught.value.details}
    assert starts == {"row 1", "row 3"}


def test_a_reconstructed_export_needs_a_job_id_and_a_row_count(tmp_path):
    rows = [log_row(1, "a" * 64, export_kind="reconstructed_from_result_page")]
    path = write_log(tmp_path / "log.tsv", rows)
    with pytest.raises(InputError):
        read_submission_log(path)
    rows[0].update(job_id="job-7", result_rows="30")
    (only,) = read_submission_log(write_log(tmp_path / "ok.tsv", rows))
    assert only.cells["job_id"] == "job-7"


def test_the_same_export_twice_is_refused(tmp_path):
    rows = [log_row(1, "a" * 64), log_row(2, "b" * 64, stp_file="c1.xlsx")]
    path = write_log(tmp_path / "log.tsv", rows)
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    assert any("c1.xlsx" in d and "1" in d and "2" in d for d in caught.value.details)


def test_a_row_with_too_many_cells_is_refused(tmp_path):
    header = "stp_file\tsubmitted_structure\tspecies\tsubmitted_date"
    path = write_text(
        tmp_path / "log.tsv", header + "\na.xlsx\tCCO\tHomo sapiens\t2026-10-21\textra\n"
    )
    with pytest.raises(InputError) as caught:
        read_submission_log(path)
    assert any("row 1" in d for d in caught.value.details)


# --- a log row that agrees with everything --------------------------------------------------------
def test_a_consistent_native_export_is_verified(tmp_path):
    outcome, digest, result = one(tmp_path)
    assert isinstance(result, BindingResult) and isinstance(outcome, SubmissionOutcome)
    assert (outcome.row, outcome.compound_id) == (1, "CMP0001")
    assert outcome.status == "verified"
    assert outcome.export_kind == "native_export"
    assert outcome.export_sha256 == digest
    assert outcome.issues == []
    assert result.orphan_issues == []


def test_no_export_kind_is_verified_but_unstated(tmp_path):
    outcome, digest, _ = one(tmp_path, {"export_kind": ""})
    assert (outcome.status, outcome.export_kind, outcome.export_sha256) == (
        "verified_kind_unstated",
        "",
        digest,
    )
    assert outcome.issues == []


def test_a_reconstructed_export_is_not_more_than_reconstructed(tmp_path):
    fields = {
        "export_kind": "reconstructed_from_result_page",
        "job_id": "job-7",
        "result_rows": "30",
    }
    outcome, digest, _ = one(tmp_path, fields)
    assert (outcome.status, outcome.export_kind, outcome.export_sha256) == (
        "reconstructed",
        "reconstructed_from_result_page",
        digest,
    )
    assert issue_view(outcome) == [
        ("warning", "submission_export_reconstructed", "submission_log", 1, "CMP0001")
    ]


def test_an_undeclared_hash_is_a_warning_and_the_actual_hash_is_recorded(tmp_path):
    outcome, digest, _ = one(tmp_path, {"result_sha256": ""})
    assert outcome.status == "verified" and outcome.export_sha256 == digest
    assert issue_view(outcome) == [
        ("warning", "submission_hash_not_declared", "submission_log", 1, "CMP0001")
    ]


def test_warnings_are_sorted_by_code(tmp_path):
    fields = {
        "result_sha256": "",
        "export_kind": "reconstructed_from_result_page",
        "job_id": "job-7",
        "result_rows": "30",
    }
    outcome, _, _ = one(tmp_path, fields)
    assert [i.code for i in outcome.issues] == [
        "submission_export_reconstructed",
        "submission_hash_not_declared",
    ]


def test_the_structure_is_compared_with_the_stripped_registered_string(tmp_path):
    outcome, _, _ = one(tmp_path, smiles="  CCO ")
    assert outcome.status == "verified"


def test_the_log_may_name_the_compound_or_leave_it_out(tmp_path):
    assert one(tmp_path, {"compound": ""})[0].status == "verified"


def test_a_pubchem_cid_is_only_compared_when_both_sides_have_one(tmp_path):
    assert one(tmp_path, {"pubchem_cid": "702"}, pubchem_cid="702")[0].status == "verified"
    assert one(tmp_path / "a", {"pubchem_cid": ""}, pubchem_cid="702")[0].status == "verified"
    assert one(tmp_path / "b", {"pubchem_cid": "702"}, pubchem_cid="")[0].status == "verified"


# --- every way a row can be rejected --------------------------------------------------------------
REJECTIONS = [
    pytest.param({"compound": "Another name"}, {}, "submission_name_mismatch", id="name"),
    pytest.param(
        {"pubchem_cid": "703"}, {"pubchem_cid": "702"}, "submission_cid_mismatch", id="cid"
    ),
    pytest.param(
        {"submitted_structure": "CCN"}, {}, "submission_structure_mismatch", id="structure"
    ),
    pytest.param({"species": "Mus musculus"}, {}, "submission_species_mismatch", id="species"),
    pytest.param({"result_sha256": "0" * 64}, {}, "submission_hash_mismatch", id="hash"),
]


@pytest.mark.parametrize("log_fields, row_fields, code", REJECTIONS)
def test_one_disagreement_rejects_the_row(tmp_path, log_fields, row_fields, code):
    outcome, digest, _ = one(tmp_path, log_fields, **row_fields)
    assert outcome.status == "rejected"
    assert outcome.export_kind == ""
    assert outcome.export_sha256 == digest
    assert issue_view(outcome) == [("error", code, "submission_log", 1, "CMP0001")]
    assert outcome.issues[0].message


def test_the_species_comes_from_the_run_config(tmp_path):
    assert (
        one(tmp_path, {"species": "Mus musculus"}, species="Mus_musculus")[0].status == "verified"
    )
    assert (
        one(tmp_path / "x", {"species": "Homo sapiens"}, species="Mus_musculus")[0].status
        == "rejected"
    )


def test_a_missing_export_file_rejects_the_row_and_records_no_hash(tmp_path):
    stp = tmp_path / "stp"
    stp.mkdir()
    rows = [compound(1, "CCO")]
    registration = registered(rows)
    log = [LogRow(1, log_row(1, "a" * 64))]
    result = bind_submissions(rows, registration.outcomes, log, stp_dir=stp, species="Homo_sapiens")
    outcome = result.outcomes[0]
    assert (outcome.status, outcome.export_sha256) == ("rejected", "")
    assert issue_view(outcome) == [
        ("error", "submission_export_missing", "submission_log", 1, "CMP0001")
    ]


@pytest.mark.parametrize("name", ["sub/c1.xlsx", "..\\c1.xlsx", "../c1.xlsx", "./c1.xlsx"])
def test_an_export_name_with_a_path_is_never_followed(tmp_path, name):
    stp = tmp_path / "stp"
    write_export(stp, "c1.xlsx")
    (stp / "sub").mkdir()
    write_export(stp / "sub", "c1.xlsx")
    rows = [compound(1, "CCO", stp_file=name)]
    registration = registered(rows)
    log = [LogRow(1, log_row(1, "a" * 64, stp_file=name))]
    outcome = bind_submissions(
        rows, registration.outcomes, log, stp_dir=stp, species="Homo_sapiens"
    ).outcomes[0]
    assert outcome.status == "rejected"
    assert [i.code for i in outcome.issues] == ["submission_export_missing"]


def test_every_disagreement_is_listed_once_in_code_order(tmp_path):
    fields = {
        "compound": "Another name",
        "submitted_structure": "CCN",
        "species": "Mus musculus",
        "result_sha256": "0" * 64,
    }
    outcome, _, _ = one(tmp_path, fields)
    assert outcome.status == "rejected"
    assert [i.code for i in outcome.issues] == [
        "submission_hash_mismatch",
        "submission_name_mismatch",
        "submission_species_mismatch",
        "submission_structure_mismatch",
    ]
    assert {i.level for i in outcome.issues} == {"error"}


def test_a_rejected_row_keeps_its_warnings(tmp_path):
    outcome, _, _ = one(tmp_path, {"submitted_structure": "CCN", "result_sha256": ""})
    assert [(i.level, i.code) for i in outcome.issues] == [
        ("error", "submission_structure_mismatch"),
        ("warning", "submission_hash_not_declared"),
    ]


# --- no record, nothing to check, and strays ------------------------------------------------------
def test_without_a_log_every_registered_structure_is_not_recorded(tmp_path):
    rows = [compound(1, "CCO"), compound(2, "CCN")]
    registration = registered(rows)
    result = bind_submissions(
        rows, registration.outcomes, None, stp_dir=None, species="Homo_sapiens"
    )
    assert [o.status for o in result.outcomes] == ["not_recorded", "not_recorded"]
    for number, outcome in enumerate(result.outcomes, start=1):
        assert (outcome.export_kind, outcome.export_sha256) == ("", "")
        assert issue_view(outcome) == [
            ("warning", "submission_record_missing", "compounds", number, f"CMP000{number}")
        ]
    assert result.orphan_issues == []


def test_a_log_without_a_row_for_the_compound_is_not_recorded(tmp_path):
    stp = tmp_path / "stp"
    write_export(stp, "c1.xlsx")
    rows = [compound(1, "CCO")]
    log = [LogRow(1, log_row(1, "a" * 64, stp_file="other.xlsx"))]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert result.outcomes[0].status == "not_recorded"
    assert [i.code for i in result.outcomes[0].issues] == ["submission_record_missing"]


def test_a_compound_without_an_export_name_is_not_recorded(tmp_path):
    stp = tmp_path / "stp"
    stp.mkdir()
    rows = [compound(1, "CCO", stp_file="")]
    log = [LogRow(1, log_row(1, "a" * 64))]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert result.outcomes[0].status == "not_recorded"
    assert [o.code for o in result.orphan_issues] == ["log_row_without_compound"]


def test_a_structure_that_was_not_registered_is_not_checked_at_all(tmp_path):
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    rows = [compound(1, "!bad"), compound(2, "")]
    log = [LogRow(1, log_row(1, digest, submitted_structure="whatever"))]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert [(o.status, o.export_kind, o.export_sha256, o.issues) for o in result.outcomes] == [
        ("not_checked", "", "", []),
        ("not_checked", "", "", []),
    ]
    assert result.orphan_issues == []


def test_log_rows_without_a_compound_are_reported_in_row_order(tmp_path):
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    rows = [compound(1, "CCO")]
    log = [
        LogRow(1, log_row(9, "z" * 64, stp_file="zzz.xlsx")),
        LogRow(2, log_row(1, digest)),
        LogRow(3, log_row(8, "y" * 64, stp_file="aaa.xlsx")),
    ]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert result.outcomes[0].status == "verified"
    assert [(i.level, i.code, i.source, i.row, i.compound_id) for i in result.orphan_issues] == [
        ("warning", "log_row_without_compound", "submission_log", 1, ""),
        ("warning", "log_row_without_compound", "submission_log", 3, ""),
    ]
    assert "zzz.xlsx" in result.orphan_issues[0].message
    assert "aaa.xlsx" in result.orphan_issues[1].message


def test_a_mixed_run_keeps_the_input_order(tmp_path):
    stp = tmp_path / "stp"
    digests = {n: write_export(stp, f"c{n}.xlsx") for n in (1, 2, 3)}
    rows = [compound(1, "CCO"), compound(2, "!bad"), compound(3, "CCO"), compound(4, "CCN")]
    log = [
        LogRow(1, log_row(1, digests[1])),
        LogRow(2, log_row(3, "0" * 64)),
    ]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert [(o.row, o.compound_id, o.status) for o in result.outcomes] == [
        (1, "CMP0001", "verified"),
        (2, "CMP0002", "not_checked"),
        (3, "CMP0003", "rejected"),
        (4, "CMP0004", "not_recorded"),
    ]


# --- the hash function and the inputs -------------------------------------------------------------
def test_the_hash_function_can_be_replaced(tmp_path):
    stp = tmp_path / "stp"
    write_export(stp, "c1.xlsx")
    seen = []

    def fake_hash(path: Path) -> str:
        seen.append(path)
        return "ab" * 32

    rows = [compound(1, "CCO")]
    log = [LogRow(1, log_row(1, "ab" * 32))]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens", hasher=fake_hash
    )
    assert seen == [stp / "c1.xlsx"]
    assert result.outcomes[0].status == "verified" and result.outcomes[0].export_sha256 == "ab" * 32


def test_the_real_hash_is_the_sha256_of_the_file(tmp_path):
    stp = tmp_path / "stp"
    write_export(stp, "c1.xlsx", "the exact bytes")
    rows = [compound(1, "CCO")]
    log = [LogRow(1, log_row(1, hashlib.sha256(b"the exact bytes").hexdigest()))]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert result.outcomes[0].status == "verified"


def test_nothing_is_hashed_when_there_is_nothing_to_check(tmp_path):
    def explode(path):
        raise AssertionError("no file should be hashed")

    stp = tmp_path / "stp"
    stp.mkdir()
    rows = [compound(1, "!bad"), compound(2, "CCO")]
    result = bind_submissions(
        rows, registered(rows).outcomes, [], stp_dir=stp, species="Homo_sapiens", hasher=explode
    )
    assert [o.status for o in result.outcomes] == ["not_checked", "not_recorded"]


def test_a_log_needs_an_export_directory(tmp_path):
    rows = [compound(1, "CCO")]
    with pytest.raises(ValueError):
        bind_submissions(rows, registered(rows).outcomes, [], stp_dir=None, species="Homo_sapiens")


def test_rows_and_registration_must_line_up(tmp_path):
    rows = [compound(1, "CCO"), compound(2, "CCN")]
    registration = registered(rows)
    with pytest.raises(ValueError):
        bind_submissions(
            rows[:1], registration.outcomes, None, stp_dir=None, species="Homo_sapiens"
        )
    with pytest.raises(ValueError):
        bind_submissions(
            [compound(5, "CCO"), compound(6, "CCN")],
            registration.outcomes,
            None,
            stp_dir=None,
            species="Homo_sapiens",
        )


def test_a_repeated_export_name_in_the_log_list_is_refused(tmp_path):
    rows = [compound(1, "CCO")]
    log = [LogRow(1, log_row(1, "a" * 64)), LogRow(2, log_row(1, "b" * 64))]
    with pytest.raises(ValueError):
        bind_submissions(
            rows, registered(rows).outcomes, log, stp_dir=tmp_path, species="Homo_sapiens"
        )


def test_binding_does_not_change_its_inputs(tmp_path):
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    rows = [compound(1, "CCO")]
    registration = registered(rows)
    log = [LogRow(1, log_row(1, digest))]
    before = ([vars(o).copy() for o in registration.outcomes], [dict(e.cells) for e in log])
    bind_submissions(rows, registration.outcomes, log, stp_dir=stp, species="Homo_sapiens")
    after = ([vars(o).copy() for o in registration.outcomes], [dict(e.cells) for e in log])
    assert before == after


def test_a_log_row_can_be_read_from_a_file_and_bound(tmp_path):
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    log = read_submission_log(write_log(tmp_path / "log.tsv", [log_row(1, digest)]))
    rows = [compound(1, "CCO")]
    result = bind_submissions(
        rows, registered(rows).outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    assert result.outcomes[0].status == "verified"
