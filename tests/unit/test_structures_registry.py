"""The structure registry: identity, supersession, warnings, file I/O (docs/upstream.md, 8.2).

`describe` is replaced by a fake everywhere, so none of these tests needs RDKit.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest
from structures_support import (
    EARLIER,
    LATER,
    NOW,
    REGISTRY_COLUMNS,
    TOOLKIT_VERSION,
    Describer,
    compound,
    fake_info,
    fake_key,
    registry_row,
    write_text,
    write_tsv,
)

from rnp.errors import InputError, SchemaViolation
from rnp.structures import (
    REGISTRY_COLUMNS as PACKAGE_COLUMNS,
)
from rnp.structures import (
    CompoundRow,
    Issue,
    check_registry,
    read_registry,
    register_structures,
    write_registry,
)
from rnp.structures import registry as registry_module
from rnp.structures.checks import structure_number


def run(rows, registry=None, describer=None, now=NOW):
    describer = describer if describer is not None else Describer()
    result = register_structures(
        rows, registry or [], toolkit_version=TOOLKIT_VERSION, now=now, describe=describer
    )
    return result, describer


def codes(outcome):
    return [issue.code for issue in outcome.issues]


def test_the_registry_columns_are_the_schema_columns():
    assert REGISTRY_COLUMNS == PACKAGE_COLUMNS
    assert registry_module.RULE_VERSION == "v0.2.0-structure-registry"


# --- a new structure ------------------------------------------------------------------------------
def test_a_new_structure_gets_a_complete_row_and_the_first_id():
    result, describer = run([compound(1, "CCO")])
    expected = registry_row("CMP0001", 1, "CCO", first=NOW, last=NOW)
    assert describer.calls == ["CCO"]
    assert result.registry == [expected]
    (outcome,) = result.outcomes
    assert outcome.status == "registered"
    assert (outcome.row, outcome.compound_id) == (1, "CMP0001")
    assert outcome.structure == expected
    assert outcome.issues == []
    assert (result.new, result.reused, result.superseded) == (0 + 1, 0, 0)


def test_the_row_carries_everything_the_description_says():
    overrides = {
        "CC(=O)[O-].[Na+]": {
            "formula": "C2H3NaO2",
            "net_charge": -1,
            "fragment_count": 2,
            "stereo_status": "partially_defined",
            "stereo_elements_specified": 1,
            "stereo_elements_total": 2,
            "inchikey": "AAAAAAAAAAAAAA-BBBBBBBBSA-M",
        }
    }
    result, _ = run([compound(3, "CC(=O)[O-].[Na+]")], describer=Describer(overrides))
    row = result.registry[0]
    assert row["formula"] == "C2H3NaO2"
    assert row["net_charge"] == "-1"
    assert row["fragment_count"] == "2"
    assert row["stereo_status"] == "partially_defined"
    assert (row["stereo_elements_specified"], row["stereo_elements_total"]) == ("1", "2")
    assert row["inchikey"] == "AAAAAAAAAAAAAA-BBBBBBBBSA-M"
    assert row["connectivity_block"] == "AAAAAAAAAAAAAA"
    assert row["compound_id"] == "CMP0003"
    assert row["standardization"] == "not_performed"
    assert row["toolkit"] == "rdkit"
    assert row["toolkit_version"] == TOOLKIT_VERSION
    assert row["rule_version"] == "v0.2.0-structure-registry"
    assert row["status"] == "current" and row["superseded_by"] == ""
    assert row["first_seen_utc"] == NOW == row["last_seen_utc"]


def test_ids_follow_the_input_order_and_the_registry_is_sorted():
    rows = [compound(1, "CCO"), compound(2, "CCN"), compound(3, "CCC")]
    result, _ = run(rows)
    assert [row["structure_id"] for row in result.registry] == ["STR0001", "STR0002", "STR0003"]
    assert [o.structure["structure_id"] for o in result.outcomes] == [
        "STR0001",
        "STR0002",
        "STR0003",
    ]
    assert [o.row for o in result.outcomes] == [1, 2, 3]
    assert result.new == 3


def test_the_result_is_sorted_even_when_the_registry_that_came_in_was_not():
    registry = [registry_row("CMP0003", 3, "CCC"), registry_row("CMP0001", 1, "CCO")]
    result, _ = run([compound(2, "CCN")], registry)
    assert [r["structure_id"] for r in result.registry] == ["STR0001", "STR0003", "STR0004"]


@pytest.mark.parametrize(
    "existing, expected",
    [
        (["STR0007"], "STR0008"),
        (["STR0003", "STR0001"], "STR0004"),
        (["STR9999"], "STR10000"),
        (["STR0042", "STR0100"], "STR0101"),
    ],
)
def test_the_next_id_is_one_more_than_the_highest(existing, expected):
    registry = [
        registry_row(f"CMP9{index:03d}", structure_number(name), f"C{index}")
        for index, name in enumerate(existing)
    ]
    result, _ = run([compound(1, "CCO")], registry)
    assert result.outcomes[0].structure["structure_id"] == expected
    assert [r["structure_id"] for r in result.registry][-1] == expected


def test_the_registry_that_was_passed_in_is_not_changed():
    registry = [registry_row("CMP0001", 1, "CCO")]
    before = copy.deepcopy(registry)
    result, _ = run([compound(1, "CCO"), compound(2, "CCN")], registry, now=LATER)
    assert registry == before
    result.registry[0]["smiles"] = "changed afterwards"
    assert registry == before


def test_the_outcome_holds_a_copy_of_the_row():
    result, _ = run([compound(1, "CCO")])
    result.outcomes[0].structure["smiles"] = "changed afterwards"
    assert result.registry[0]["smiles"] == "CCO"


# --- reuse ----------------------------------------------------------------------------------------
def test_a_registered_structure_is_reused_without_describing_it_again():
    registry = [registry_row("CMP0001", 1, "CCO", first=EARLIER, last=EARLIER)]
    result, describer = run([compound(1, "CCO")], registry, now=LATER)
    assert describer.calls == []
    (row,) = result.registry
    assert row["structure_id"] == "STR0001"
    assert row["first_seen_utc"] == EARLIER
    assert row["last_seen_utc"] == LATER
    assert result.outcomes[0].structure == row
    assert (result.new, result.reused, result.superseded) == (0, 1, 0)
    assert result.outcomes[0].issues == []


def test_last_seen_never_goes_backwards():
    registry = [registry_row("CMP0001", 1, "CCO", first=EARLIER, last=LATER)]
    result, _ = run([compound(1, "CCO")], registry, now=NOW)
    assert result.registry[0]["last_seen_utc"] == LATER


def test_the_same_string_for_another_compound_is_a_new_structure():
    registry = [registry_row("CMP0001", 1, "CCO")]
    result, describer = run([compound(2, "CCO")], registry)
    assert describer.calls == ["CCO"]
    assert [r["structure_id"] for r in result.registry] == ["STR0001", "STR0002"]
    assert result.registry[1]["compound_id"] == "CMP0002"


def test_a_structure_of_another_compound_is_not_touched():
    registry = [registry_row("CMP0001", 1, "CCO", last=EARLIER)]
    result, _ = run([compound(2, "CCN")], registry, now=LATER)
    assert result.registry[0] == registry[0]


# --- a changed structure --------------------------------------------------------------------------
def test_a_changed_string_supersedes_the_old_structure():
    registry = [registry_row("CMP0001", 1, "CCO", first=EARLIER, last=EARLIER)]
    result, describer = run([compound(1, "CCN")], registry, now=LATER)
    old, new = result.registry
    assert describer.calls == ["CCN"]
    assert (old["structure_id"], old["status"], old["superseded_by"]) == (
        "STR0001",
        "superseded",
        "STR0002",
    )
    assert old["last_seen_utc"] == EARLIER and old["first_seen_utc"] == EARLIER
    assert (new["structure_id"], new["status"], new["smiles"]) == ("STR0002", "current", "CCN")
    assert new["first_seen_utc"] == LATER == new["last_seen_utc"]
    (outcome,) = result.outcomes
    assert outcome.structure == new
    assert codes(outcome) == ["structure_changed"]
    changed = outcome.issues[0]
    assert (changed.level, changed.source, changed.row, changed.compound_id) == (
        "warning",
        "compounds",
        1,
        "CMP0001",
    )
    message = outcome.issues[0].message
    assert "STR0001" in message and "STR0002" in message
    assert (result.new, result.reused, result.superseded) == (1, 0, 1)


def test_two_changes_in_a_row_keep_every_old_structure():
    registry = [registry_row("CMP0001", 1, "CCO")]
    first, _ = run([compound(1, "CCN")], registry, now=NOW)
    second, _ = run([compound(1, "CCC")], first.registry, now=LATER)
    assert [(r["structure_id"], r["status"], r["superseded_by"]) for r in second.registry] == [
        ("STR0001", "superseded", "STR0002"),
        ("STR0002", "superseded", "STR0003"),
        ("STR0003", "current", ""),
    ]
    assert check_registry(second.registry) == []


# --- going back to an old structure ---------------------------------------------------------------
def test_returning_to_an_old_string_restores_the_old_id():
    registry = [
        registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0002"),
        registry_row("CMP0001", 2, "CCN"),
    ]
    result, describer = run([compound(1, "CCO")], registry, now=LATER)
    old, new = result.registry
    assert describer.calls == []
    assert (old["status"], old["superseded_by"], old["last_seen_utc"]) == ("current", "", LATER)
    assert (new["status"], new["superseded_by"], new["last_seen_utc"]) == (
        "superseded",
        "STR0001",
        EARLIER,
    )
    (outcome,) = result.outcomes
    assert outcome.structure == old
    assert codes(outcome) == ["structure_reactivated"]
    back = outcome.issues[0]
    assert (back.level, back.source, back.row, back.compound_id) == (
        "warning",
        "compounds",
        1,
        "CMP0001",
    )
    assert "STR0001" in back.message
    assert (result.new, result.reused, result.superseded) == (0, 1, 1)
    assert check_registry(result.registry) == []


def test_returning_to_an_old_string_when_nothing_is_current():
    registry = [registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0009")]
    result, describer = run([compound(1, "CCO")], registry, now=LATER)
    (row,) = result.registry
    assert describer.calls == []
    assert (row["status"], row["superseded_by"], row["last_seen_utc"]) == ("current", "", LATER)
    assert codes(result.outcomes[0]) == ["structure_reactivated"]
    assert (result.new, result.reused, result.superseded) == (0, 1, 0)


# --- strings that cannot be registered ------------------------------------------------------------
@pytest.mark.parametrize("text", ["", " ", "\t", " \t "])
def test_an_empty_cell_is_a_missing_structure(text):
    result, describer = run([compound(1, text)])
    (outcome,) = result.outcomes
    assert describer.calls == []
    assert outcome.status == "not_registered" and outcome.structure is None
    assert [(i.level, i.code) for i in outcome.issues] == [("error", "missing_structure")]
    assert result.registry == []
    assert (result.new, result.reused, result.superseded) == (0, 0, 0)


def test_a_string_that_cannot_be_described_is_an_invalid_smiles():
    result, describer = run([compound(4, "!bad")])
    (outcome,) = result.outcomes
    assert describer.calls == ["!bad"]
    assert outcome.status == "not_registered" and outcome.structure is None
    (issue,) = outcome.issues
    assert (issue.level, issue.code, issue.source) == ("error", "invalid_smiles", "compounds")
    assert (issue.row, issue.compound_id) == (4, "CMP0004")
    assert "!bad" in issue.message
    assert result.registry == []


def test_a_failed_row_does_not_stop_the_others():
    rows = [compound(1, "CCO"), compound(2, "!bad"), compound(3, ""), compound(4, "CCN")]
    result, _ = run(rows)
    assert [o.status for o in result.outcomes] == [
        "registered",
        "not_registered",
        "not_registered",
        "registered",
    ]
    assert [r["structure_id"] for r in result.registry] == ["STR0001", "STR0002"]
    assert result.registry[1]["compound_id"] == "CMP0004"


def test_a_failed_string_leaves_the_current_structure_alone():
    registry = [registry_row("CMP0001", 1, "CCO", last=EARLIER)]
    result, _ = run([compound(1, "!bad")], registry, now=LATER)
    assert result.registry == registry


# --- whitespace -----------------------------------------------------------------------------------
def test_surrounding_whitespace_is_removed_and_reported():
    result, describer = run([compound(1, "  CCO\t ")])
    (outcome,) = result.outcomes
    assert describer.calls == ["CCO"]
    assert result.registry[0]["smiles"] == "CCO"
    (issue,) = outcome.issues
    assert (issue.level, issue.code, issue.source) == (
        "warning",
        "smiles_whitespace_trimmed",
        "compounds",
    )


def test_a_trimmed_string_finds_its_registered_structure():
    registry = [registry_row("CMP0001", 1, "CCO")]
    result, describer = run([compound(1, " CCO ")], registry)
    assert describer.calls == []
    assert codes(result.outcomes[0]) == ["smiles_whitespace_trimmed"]
    assert len(result.registry) == 1


def test_an_invalid_trimmed_string_reports_the_error_before_the_warning():
    result, _ = run([compound(1, "  !bad ")])
    assert [(i.level, i.code) for i in result.outcomes[0].issues] == [
        ("error", "invalid_smiles"),
        ("warning", "smiles_whitespace_trimmed"),
    ]


# --- warnings that come from the stored description -----------------------------------------------
WARNING_CASES = [
    pytest.param(
        {"stereo_status": "partially_defined", "specified": 1, "total": 2},
        ["stereo_undefined"],
        id="partial",
    ),
    pytest.param({"stereo_status": "undefined", "total": 1}, ["stereo_undefined"], id="undefined"),
    pytest.param({"stereo_status": "defined", "specified": 1, "total": 1}, [], id="defined"),
    pytest.param({}, [], id="no stereo elements"),
    pytest.param({"fragments": 2}, ["multi_fragment"], id="two fragments"),
    pytest.param({"charge": -1}, ["charged_structure"], id="negative"),
    pytest.param({"charge": 2}, ["charged_structure"], id="positive"),
    pytest.param(
        {"fragments": 3, "charge": 1, "stereo_status": "undefined", "total": 2},
        ["charged_structure", "multi_fragment", "stereo_undefined"],
        id="all three",
    ),
]


@pytest.mark.parametrize("fields, expected", WARNING_CASES)
def test_warnings_for_a_reused_structure(fields, expected):
    registry = [registry_row("CMP0001", 1, "CCO", **fields)]
    result, _ = run([compound(1, "CCO")], registry)
    assert codes(result.outcomes[0]) == expected
    assert all(issue.level == "warning" for issue in result.outcomes[0].issues)


@pytest.mark.parametrize("fields, expected", WARNING_CASES)
def test_warnings_for_a_new_structure(fields, expected):
    overrides = {
        "CCO": {
            "stereo_status": fields.get("stereo_status", "none_present"),
            "stereo_elements_specified": fields.get("specified", 0),
            "stereo_elements_total": fields.get("total", 0),
            "fragment_count": fields.get("fragments", 1),
            "net_charge": fields.get("charge", 0),
        }
    }
    result, _ = run([compound(1, "CCO")], describer=Describer(overrides))
    assert codes(result.outcomes[0]) == expected


# --- structures shared between compounds ----------------------------------------------------------
SAME_KEY = "AAAAAAAAAAAAAA-BBBBBBBBSA-N"
OTHER_STEREO = "AAAAAAAAAAAAAA-CCCCCCCCSA-N"


def test_the_same_inchikey_for_two_compounds_is_reported_on_both():
    describer = Describer({"CCO": {"inchikey": SAME_KEY}, "OCC": {"inchikey": SAME_KEY}})
    result, _ = run([compound(1, "CCO"), compound(2, "OCC")], describer=describer)
    first, second = result.outcomes
    assert codes(first) == ["shared_structure"] and codes(second) == ["shared_structure"]
    assert "CMP0002" in first.issues[0].message and "CMP0001" in second.issues[0].message
    for outcome in (first, second):
        issue = outcome.issues[0]
        assert (issue.level, issue.source, issue.row, issue.compound_id) == (
            "warning",
            "compounds",
            outcome.row,
            outcome.compound_id,
        )
    assert [r["structure_id"] for r in result.registry] == ["STR0001", "STR0002"]


def test_a_current_structure_of_a_compound_outside_the_input_counts():
    registry = [registry_row("CMP0009", 1, "OCC", inchikey=SAME_KEY)]
    describer = Describer({"CCO": {"inchikey": SAME_KEY}})
    result, _ = run([compound(1, "CCO")], registry, describer=describer)
    assert codes(result.outcomes[0]) == ["shared_structure"]
    assert "CMP0009" in result.outcomes[0].issues[0].message


def test_a_superseded_structure_of_another_compound_does_not_count():
    registry = [
        registry_row(
            "CMP0009", 1, "OCC", inchikey=SAME_KEY, status="superseded", superseded_by="STR0002"
        ),
        registry_row("CMP0009", 2, "CCCC"),
    ]
    describer = Describer({"CCO": {"inchikey": SAME_KEY}})
    result, _ = run([compound(1, "CCO")], registry, describer=describer)
    assert codes(result.outcomes[0]) == []


def test_the_same_key_inside_one_compound_is_not_shared():
    registry = [registry_row("CMP0001", 1, "OCC", inchikey=SAME_KEY)]
    describer = Describer({"CCO": {"inchikey": SAME_KEY}})
    result, _ = run([compound(1, "CCO")], registry, describer=describer)
    assert codes(result.outcomes[0]) == ["structure_changed"]


def test_same_connectivity_with_other_stereo_is_reported_on_both():
    describer = Describer({"A": {"inchikey": SAME_KEY}, "B": {"inchikey": OTHER_STEREO}})
    result, _ = run([compound(1, "A"), compound(2, "B")], describer=describer)
    first, second = result.outcomes
    assert codes(first) == ["same_connectivity_different_stereo"]
    assert codes(second) == ["same_connectivity_different_stereo"]
    assert "CMP0002" in first.issues[0].message and "CMP0001" in second.issues[0].message
    for outcome in (first, second):
        issue = outcome.issues[0]
        assert (issue.level, issue.source, issue.row, issue.compound_id) == (
            "warning",
            "compounds",
            outcome.row,
            outcome.compound_id,
        )


def test_same_connectivity_is_not_reported_between_a_compounds_own_versions():
    registry = [registry_row("CMP0001", 1, "A", inchikey=SAME_KEY)]
    describer = Describer({"B": {"inchikey": OTHER_STEREO}})
    result, _ = run([compound(1, "B")], registry, describer=describer)
    assert codes(result.outcomes[0]) == ["structure_changed"]


def test_different_connectivity_is_not_reported():
    describer = Describer()
    result, _ = run([compound(1, "CCO"), compound(2, "CCN")], describer=describer)
    assert [codes(o) for o in result.outcomes] == [[], []]


# --- order and shape of the issues ----------------------------------------------------------------
def test_issues_are_sorted_errors_first_then_by_code():
    overrides = {
        "CCO": {
            "inchikey": SAME_KEY,
            "fragment_count": 2,
            "net_charge": 1,
            "stereo_status": "undefined",
            "stereo_elements_total": 1,
        },
        "OCC": {"inchikey": SAME_KEY},
    }
    result, _ = run([compound(1, " CCO"), compound(2, "OCC")], describer=Describer(overrides))
    assert codes(result.outcomes[0]) == [
        "charged_structure",
        "multi_fragment",
        "shared_structure",
        "smiles_whitespace_trimmed",
        "stereo_undefined",
    ]


def test_an_issue_has_the_audit_fields():
    result, _ = run([compound(7, "")])
    issue = result.outcomes[0].issues[0]
    assert isinstance(issue, Issue)
    assert issue.as_dict() == {
        "level": "error",
        "code": "missing_structure",
        "source": "compounds",
        "row": 7,
        "compound_id": "CMP0007",
        "message": issue.message,
    }
    assert issue.message


def test_the_same_compound_twice_is_refused():
    with pytest.raises(ValueError):
        run([compound(1, "CCO"), compound(1, "CCN")])


def test_an_empty_input_changes_nothing():
    registry = [registry_row("CMP0001", 1, "CCO")]
    result, describer = run([], registry)
    assert result.outcomes == [] and result.registry == registry and describer.calls == []
    assert (result.new, result.reused, result.superseded) == (0, 0, 0)


# --- the description must fit the registry schema -------------------------------------------------
@pytest.mark.parametrize(
    "field, value",
    [
        ("inchikey", "not-an-inchikey"),
        ("formula", ""),
        ("net_charge", 1.5),
        ("stereo_status", "unknown"),
    ],
)
def test_a_description_that_does_not_fit_the_schema_is_an_internal_error(field, value):
    describer = Describer({"CCO": {field: value}})
    with pytest.raises(SchemaViolation) as caught:
        run([compound(1, "CCO")], describer=describer)
    assert caught.value.exit_code == 1


# --- the default describer ------------------------------------------------------------------------
def test_without_a_describer_the_adapter_is_used_for_new_structures(monkeypatch):
    seen = Describer()
    monkeypatch.setattr("rnp.structures.chem.describe_smiles", seen)
    result = register_structures([compound(1, "CCO")], [], toolkit_version=TOOLKIT_VERSION, now=NOW)
    assert seen.calls == ["CCO"]
    assert result.registry[0]["smiles"] == "CCO"


def test_without_a_describer_a_registered_structure_needs_no_adapter(monkeypatch):
    def explode(smiles):
        raise AssertionError("the adapter must not be called")

    monkeypatch.setattr("rnp.structures.chem.describe_smiles", explode)
    registry = [registry_row("CMP0001", 1, "CCO")]
    result = register_structures(
        [compound(1, "CCO")], registry, toolkit_version=TOOLKIT_VERSION, now=LATER
    )
    assert result.reused == 1


def test_the_value_types_are_immutable():
    issue = Issue("error", "missing_structure", "compounds", 1, "CMP0001", "no SMILES string")
    values = [
        (compound(1, "CCO"), "row"),
        (issue, "level"),
        (fake_info("CCO"), "smiles"),
    ]
    for value, attribute in values:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(value, attribute, 99)


def test_the_compound_row_defaults():
    row = CompoundRow(1, "CMP0001", "all", "Ethanol", "e.xlsx", "CCO")
    assert row.pubchem_cid == ""


# --- reading and writing the registry file --------------------------------------------------------
def sample_registry():
    return [
        registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0002"),
        registry_row("CMP0001", 2, "CCN", first=NOW, last=LATER),
        registry_row("CMP0002", 3, "CCC"),
    ]


def test_a_missing_registry_file_is_an_empty_registry(tmp_path):
    assert read_registry(tmp_path / "nowhere" / "structure_registry.tsv") == []


def test_a_header_only_file_is_an_empty_registry(tmp_path):
    path = write_text(tmp_path / "r.tsv", "\t".join(REGISTRY_COLUMNS) + "\n")
    assert read_registry(path) == []


def test_a_header_only_file_with_other_columns_is_refused(tmp_path):
    path = write_text(tmp_path / "r.tsv", "structure_id\tcompound_id\n")
    with pytest.raises(InputError):
        read_registry(path)


def test_write_then_read_gives_the_same_rows(tmp_path):
    path = tmp_path / "registry" / "structure_registry.tsv"
    write_registry(path, sample_registry())
    assert read_registry(path) == sample_registry()


def test_the_file_is_sorted_tab_separated_lf_and_has_the_columns_in_order(tmp_path):
    path = tmp_path / "structure_registry.tsv"
    write_registry(path, list(reversed(sample_registry())))
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n") and not raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8").splitlines()
    assert lines[0] == "\t".join(REGISTRY_COLUMNS)
    assert [line.split("\t")[0] for line in lines[1:]] == ["STR0001", "STR0002", "STR0003"]
    assert all(len(line.split("\t")) == len(REGISTRY_COLUMNS) for line in lines)


def test_writing_leaves_no_temporary_file_behind(tmp_path):
    write_registry(tmp_path / "r.tsv", sample_registry())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.tsv"]


def test_an_empty_registry_is_written_as_a_header(tmp_path):
    write_registry(tmp_path / "r.tsv", [])
    assert (tmp_path / "r.tsv").read_text(encoding="utf-8") == "\t".join(REGISTRY_COLUMNS) + "\n"
    assert read_registry(tmp_path / "r.tsv") == []


def test_the_result_of_a_run_can_be_written_and_read_back(tmp_path):
    result, _ = run([compound(1, "CCO"), compound(2, "CCN"), compound(3, "")])
    write_registry(tmp_path / "r.tsv", result.registry)
    assert read_registry(tmp_path / "r.tsv") == result.registry


def test_a_registry_with_other_columns_is_refused(tmp_path):
    columns = list(REGISTRY_COLUMNS)
    columns[0], columns[1] = columns[1], columns[0]
    path = write_tsv(tmp_path / "r.tsv", columns, [])
    write_text(path, "\t".join(columns) + "\n" + "\t".join("x" for _ in columns) + "\n")
    with pytest.raises(InputError) as caught:
        read_registry(path)
    assert "r.tsv" in caught.value.message
    assert any("structure_id" in detail for detail in caught.value.details)


def test_an_invalid_row_names_its_row_and_column(tmp_path):
    rows = sample_registry()
    rows[1]["inchikey"] = "lower-case-key"
    path = write_tsv(tmp_path / "r.tsv", REGISTRY_COLUMNS, rows)
    with pytest.raises(InputError) as caught:
        read_registry(path)
    assert caught.value.exit_code == 2
    assert any(
        detail.startswith("row 2:") and "inchikey" in detail for detail in caught.value.details
    )


def test_an_inconsistent_registry_is_refused_with_the_reason(tmp_path):
    rows = sample_registry()
    rows[0].update(status="current", superseded_by="")
    path = write_tsv(tmp_path / "r.tsv", REGISTRY_COLUMNS, rows)
    with pytest.raises(InputError) as caught:
        read_registry(path)
    assert any("2 current structures" in detail for detail in caught.value.details)


def test_writing_an_invalid_row_is_an_internal_error_and_writes_nothing(tmp_path):
    rows = sample_registry()
    rows[0]["inchikey"] = "bad"
    with pytest.raises(SchemaViolation):
        write_registry(tmp_path / "r.tsv", rows)
    assert not (tmp_path / "r.tsv").exists()


def test_the_problems_of_a_registry_to_write_name_their_rows(tmp_path):
    rows = sample_registry()
    rows[1]["inchikey"] = "bad"
    with pytest.raises(SchemaViolation) as caught:
        write_registry(tmp_path / "r.tsv", rows)
    assert any(d.startswith("row 2:") and "inchikey" in d for d in caught.value.details)
    assert not any(d.startswith("row 1:") for d in caught.value.details)


def test_the_row_numbers_of_a_write_problem_follow_the_order_given(tmp_path):
    rows = list(reversed(sample_registry()))
    rows[0]["inchikey"] = "bad"
    with pytest.raises(SchemaViolation) as caught:
        write_registry(tmp_path / "r.tsv", rows)
    assert [d.split(":")[0] for d in caught.value.details] == ["row 1"]


def test_a_malformed_structure_id_is_a_schema_violation_not_a_crash(tmp_path):
    rows = sample_registry()
    rows[1]["structure_id"] = "STR2"
    with pytest.raises(SchemaViolation) as caught:
        write_registry(tmp_path / "r.tsv", rows)
    assert any(d.startswith("row 2:") and "structure_id" in d for d in caught.value.details)


def test_writing_an_inconsistent_registry_is_an_internal_error(tmp_path):
    rows = sample_registry() + [registry_row("CMP0003", 1, "CCCC")]
    with pytest.raises(SchemaViolation):
        write_registry(tmp_path / "r.tsv", rows)
    assert not (tmp_path / "r.tsv").exists()


# --- the cross-row checks -------------------------------------------------------------------------
def test_a_consistent_registry_has_no_problems():
    assert check_registry(sample_registry()) == []
    assert check_registry([]) == []


def problem_for(rows):
    problems = check_registry(rows)
    assert len(problems) == 1, problems
    return problems[0]


def test_a_repeated_structure_id():
    rows = sample_registry()
    rows[2]["structure_id"] = "STR0001"
    problems = check_registry(rows)
    assert any("STR0001" in p and "2 times" in p for p in problems)


def test_the_same_string_registered_twice_for_one_compound():
    rows = [registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0002")]
    rows.append(registry_row("CMP0001", 2, "CCO"))
    assert any("CMP0001" in p and "CCO" in p and "2 times" in p for p in check_registry(rows))


def test_two_current_structures_for_one_compound():
    rows = [registry_row("CMP0001", 1, "CCO"), registry_row("CMP0001", 2, "CCN")]
    assert "CMP0001 has 2 current structures" in problem_for(rows)


def test_a_compound_without_a_current_structure():
    rows = [registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0002")]
    rows.append(registry_row("CMP0001", 2, "CCN", status="superseded", superseded_by="STR0001"))
    assert "CMP0001 has 0 current structures" in problem_for(rows)


def test_superseded_by_must_exist():
    rows = [
        registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0009"),
        registry_row("CMP0001", 2, "CCN"),
    ]
    assert "STR0009 is not in the registry" in problem_for(rows)


def test_superseded_by_must_belong_to_the_same_compound():
    rows = [
        registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0003"),
        registry_row("CMP0001", 2, "CCN"),
        registry_row("CMP0002", 3, "CCC"),
    ]
    assert "belongs to another compound" in problem_for(rows)


def test_superseded_by_must_not_point_to_itself():
    rows = [
        registry_row("CMP0001", 1, "CCO", status="superseded", superseded_by="STR0001"),
        registry_row("CMP0001", 2, "CCN"),
    ]
    assert "points to itself" in problem_for(rows)


def test_the_connectivity_block_must_be_the_first_block_of_the_key():
    rows = [registry_row("CMP0001", 1, "CCO")]
    rows[0]["connectivity_block"] = "ZZZZZZZZZZZZZZ"
    assert "connectivity_block" in problem_for(rows)


def test_defined_means_every_element_is_specified():
    rows = [registry_row("CMP0001", 1, "CCO", stereo_status="defined", specified=1, total=2)]
    assert "defined" in problem_for(rows) and "1 of 2" in problem_for(rows)


def test_partially_defined_means_fewer_specified_than_elements():
    rows = [
        registry_row("CMP0001", 1, "CCO", stereo_status="partially_defined", specified=2, total=2)
    ]
    assert "partially_defined" in problem_for(rows)


def test_a_structure_cannot_be_seen_for_the_last_time_before_the_first():
    rows = [registry_row("CMP0001", 1, "CCO", first=LATER, last=NOW)]
    assert "first_seen_utc" in problem_for(rows)


def test_a_problem_names_the_position_and_the_id_of_its_row():
    rows = [
        registry_row("CMP0001", 1, "CCO"),
        registry_row("CMP0002", 2, "CCN", first=LATER, last=NOW),
    ]
    assert problem_for(rows).startswith("row 2 (STR0002): ")


def test_structure_number():
    assert structure_number("STR0042") == 42
    assert structure_number("STR10000") == 10000
    for bad in ["STR042", "str0042", "CMP0042", ""]:
        with pytest.raises(ValueError):
            structure_number(bad)


def test_fake_keys_are_well_formed():
    assert fake_key("CCO") != fake_key("CCN")
    assert fake_key("CCO", "B").split("-")[0] == fake_key("CCO").split("-")[0]
    assert fake_key("CCO", "B") != fake_key("CCO")


def test_the_registry_is_a_path_friendly_function(tmp_path: Path):
    path = tmp_path / "a" / "b" / "r.tsv"
    write_registry(path, sample_registry())
    assert path.is_file()
