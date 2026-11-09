"""Contract tests for the entry A artifact schemas (docs/upstream.md, section 8).

Four schemas describe the artifacts of the structure-aware compound registration: one row of the
submission log (an input), one row of the structure registry (persistent state), one row of
compound_structures.tsv (a stage output) and the stage audit. Every document below is synthetic and
every hash is computed here from a made-up body.

Each *_BAD case changes exactly one thing in a document that is valid on its own, so a rejection can
only come from that change; each *_GOOD case must stay valid. The baselines are checked first.
"""

from __future__ import annotations

import hashlib

import pytest
from jsonschema import Draft202012Validator

from rnp.config import load_schema

BASE_URL = "https://github.com/zym137706-ops/reproducible-network-pharmacology/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_NAMES = [
    "submission_log_row",
    "structure_registry_row",
    "compound_structures_row",
    "compounds_audit",
]
DELETE = object()
_VALIDATORS: dict[str, Draft202012Validator] = {}

ERRORS = [
    "missing_structure",
    "invalid_smiles",
    "submission_structure_mismatch",
    "submission_hash_mismatch",
    "submission_species_mismatch",
    "submission_export_missing",
    "submission_name_mismatch",
    "submission_cid_mismatch",
]
STRUCTURE_ERRORS = ERRORS[:2]
SUBMISSION_ERRORS = ERRORS[2:]
ROW_WARNINGS = [
    "shared_structure",
    "same_connectivity_different_stereo",
    "stereo_undefined",
    "multi_fragment",
    "charged_structure",
    "smiles_whitespace_trimmed",
    "structure_changed",
    "structure_reactivated",
    "submission_record_missing",
    "submission_export_reconstructed",
    "submission_hash_not_declared",
]
WARNINGS = ROW_WARNINGS + ["log_row_without_compound"]
FREE_ROW_WARNINGS = [
    code
    for code in ROW_WARNINGS
    if code not in ("submission_record_missing", "submission_export_reconstructed")
]
STEREO = ["none_present", "defined", "partially_defined", "undefined"]
LOG_REQUIRED = ["stp_file", "submitted_structure", "species", "submitted_date"]
LOG_COLUMNS = [
    "compound",
    "pubchem_cid",
    "stp_file",
    "submitted_structure",
    "structure_source",
    "species",
    "submitted_date",
    "result_file",
    "retrieved_date",
    "operator",
    "result_sha256",
    "notes",
    "submitted_date_precision",
    "retrieved_date_basis",
    "retrieved_date_precision",
    "time_zone_windows_id",
    "utc_offset",
    "result_url",
    "job_id",
    "operator_identity",
    "submission_method",
    "submission_evidence",
    "export_kind",
    "result_rows",
]
REGISTRY_COLUMNS = [
    "structure_id",
    "compound_id",
    "smiles",
    "inchikey",
    "connectivity_block",
    "formula",
    "net_charge",
    "fragment_count",
    "stereo_status",
    "stereo_elements_specified",
    "stereo_elements_total",
    "standardization",
    "toolkit",
    "toolkit_version",
    "rule_version",
    "status",
    "superseded_by",
    "first_seen_utc",
    "last_seen_utc",
]
STRUCTURES_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "row_status",
    "structure_status",
    "structure_id",
    "smiles",
    "inchikey",
    "stereo_status",
    "submission_status",
    "export_kind",
    "export_sha256",
    "issue_codes",
]
AUDIT_REQUIRED = [
    "schema_version",
    "generated_by",
    "stage_status",
    "identity_mode",
    "config",
    "inputs",
    "toolkit",
    "rule_versions",
    "summary",
    "issues",
    "registries",
    "notes",
    "compound_structures_sha256",
]
SUMMARY_FIELDS = [
    "rows",
    "rows_accepted",
    "rows_quarantined",
    "rows_name_only",
    "structures_new",
    "structures_reused",
    "structures_superseded",
    "submissions_verified",
    "submissions_reconstructed",
    "submissions_not_recorded",
    "submissions_rejected",
    "errors",
    "warnings",
]
ISSUE_FIELDS = ["level", "code", "source", "row", "compound_id", "message"]
EXPORT_BODY = "synthetic STP export of ethanol"
EXPORT_HASH = hashlib.sha256(EXPORT_BODY.encode("utf-8")).hexdigest()


def validator(name: str) -> Draft202012Validator:
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(load_schema(name))
    return _VALIDATORS[name]


def is_valid(name: str, document: object) -> bool:
    return validator(name).is_valid(document)


def problems(name: str, document: object) -> list[str]:
    return [error.message[:120] for error in validator(name).iter_errors(document)]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def edited(builder, *edits):
    """Build a document and apply (path, value) edits; DELETE removes the key."""
    document = builder()
    for path, value in edits:
        target = document
        for key in path[:-1]:
            target = target[key]
        if value is DELETE:
            del target[path[-1]]
        else:
            target[path[-1]] = value
    return document


def case(case_id: str, builder, *edits):
    return pytest.param(builder, edits, id=case_id)


def variants(prefix: str, builder, path: tuple, values: list):
    return [case(f"{prefix} {value!r}", builder, (path, value)) for value in values]


def builders_of(cases: list) -> list:
    unique = []
    for param in cases:
        if param.values[0] not in unique:
            unique.append(param.values[0])
    return unique


# --- submission log row ---------------------------------------------------------------------------
def log_minimal() -> dict:
    return {
        "stp_file": "ethanol.xlsx",
        "submitted_structure": "CCO",
        "species": "Homo sapiens",
        "submitted_date": "2026-10-21",
    }


def log_full() -> dict:
    return {
        "compound": "Ethanol",
        "pubchem_cid": "702",
        "stp_file": "ethanol.xlsx",
        "submitted_structure": "CCO",
        "structure_source": "PubChem CID 702",
        "species": "Homo sapiens",
        "submitted_date": "2026-10-21",
        "result_file": "inputs/stp/ethanol.xlsx",
        "retrieved_date": "2026-10-21T14:13:22+08:00",
        "operator": "manual_by_user",
        "result_sha256": EXPORT_HASH,
        "notes": "Structure and species confirmed by the researcher",
        "submitted_date_precision": "date",
        "retrieved_date_basis": "user_approved_file_LastWriteTime_proxy",
        "retrieved_date_precision": "filesystem_timestamp_seconds",
        "time_zone_windows_id": "China Standard Time",
        "utc_offset": "+08:00",
        "result_url": "not_saved",
        "job_id": "not_saved",
        "operator_identity": "not_supplied",
        "submission_method": "manual",
        "submission_evidence": "user_confirmation",
        "export_kind": "native_export",
        "result_rows": "30",
    }


def log_empty_cells() -> dict:
    row = {name: "" for name in LOG_COLUMNS}
    row.update(log_minimal())
    return row


def log_reconstructed() -> dict:
    row = log_full()
    row.update(export_kind="reconstructed_from_result_page", job_id="job-7f3a21", result_rows="30")
    return row


LOG_GOOD = [
    case("minimal", log_minimal),
    case("every known column", log_full),
    case("every optional cell empty", log_empty_cells),
    case("reconstructed export with a job id", log_reconstructed),
    *variants("species", log_minimal, ("species",), ["Mus musculus"]),
    *variants(
        "submitted structure",
        log_minimal,
        ("submitted_structure",),
        ["C[C@H](N)C(=O)[O-]", "[Na+].CC(=O)[O-]", "C/C=C/C", "c1ccccc1", "[2H]C"],
    ),
    *variants(
        "stp_file",
        log_minimal,
        ("stp_file",),
        ["my export (1).xlsx", "caf" + chr(233) + ".xlsx", "a", "inputs/stp/x.xlsx"],
    ),
    case("extra column", log_minimal, (("lab_note",), "checked twice")),
    case("extra column left empty", log_minimal, (("lab_note",), "")),
    case("native export keeps a job id of not_saved", log_full, (("job_id",), "not_saved")),
    case(
        "reconstructed export may also carry a result url",
        log_reconstructed,
        (("result_url",), "https://example.org/job/7f3a21"),
    ),
    case(
        "job id that merely starts with not_saved",
        log_reconstructed,
        (("job_id",), "not_saved_2"),
    ),
    case("declared hash left empty", log_full, (("result_sha256",), "")),
    case("export kind left empty", log_full, (("export_kind",), "")),
    case("large row count", log_full, (("result_rows",), "100")),
    case("pubchem_cid left empty", log_full, (("pubchem_cid",), "")),
]

LOG_BAD = [case(f"missing {name}", log_minimal, ((name,), DELETE)) for name in LOG_REQUIRED]
LOG_BAD += variants(
    "stp_file",
    log_minimal,
    ("stp_file",),
    [
        "",
        " ethanol.xlsx",
        "ethanol.xlsx ",
        "etha\tnol.xlsx",
        "etha\nnol.xlsx",
        "\nethanol.xlsx",
        5,
        None,
    ],
)
LOG_BAD += variants(
    "submitted_structure",
    log_minimal,
    ("submitted_structure",),
    ["", "CC O", " CCO", "CCO ", "CC\tO", "CC\nO", "\nCCO", 5, None],
)
LOG_BAD += variants(
    "species",
    log_minimal,
    ("species",),
    ["Homo_sapiens", "homo sapiens", "human", "", "Rattus norvegicus", None],
)
LOG_BAD += variants(
    "submitted_date",
    log_minimal,
    ("submitted_date",),
    [
        "2026-10-21T14:13:22+08:00",
        "2026-13-01",
        "2026-00-10",
        "2026-10-32",
        "2026-10-00",
        "21/10/2026",
        "2026-1-5",
        "",
        " 2026-10-21",
        20261021,
        None,
    ],
)
LOG_BAD += variants(
    "result_sha256",
    log_full,
    ("result_sha256",),
    [
        EXPORT_HASH.upper(),
        EXPORT_HASH[:-1],
        EXPORT_HASH + "0",
        "sha256:" + EXPORT_HASH,
        EXPORT_HASH + " ",
        "g" + EXPORT_HASH[1:],
        5,
        None,
    ],
)
LOG_BAD += variants(
    "export_kind",
    log_full,
    ("export_kind",),
    ["native", "Native_Export", "reconstructed", " native_export", 1, None],
)
LOG_BAD += variants(
    "pubchem_cid", log_full, ("pubchem_cid",), ["abc", "-5", "5280343.0", " 5280343", 702, None]
)
LOG_BAD += variants(
    "result_rows", log_full, ("result_rows",), ["0", "-3", "3.5", "abc", " 30", 30, None]
)
LOG_BAD += variants("notes", log_full, ("notes",), ["a\tb", "a\nb", " lead", "trail ", 5, None])
LOG_BAD += variants("compound", log_full, ("compound",), [" Ethanol", "Ethanol ", "Eth\tanol"])
LOG_BAD += variants("structure_source", log_full, ("structure_source",), ["PubChem\nCID 702", 5])
LOG_BAD += variants("operator", log_full, ("operator",), ["manual\tby_user", None])
LOG_BAD += variants("result_file", log_full, ("result_file",), ["inputs/stp\t/x.xlsx", " x.xlsx"])
LOG_BAD += variants(
    "extra column", log_minimal, ("lab_note",), [5, None, "a\nb", "a\tb", ["x"], True]
)
LOG_BAD += [
    case("reconstructed without job_id", log_reconstructed, (("job_id",), DELETE)),
    case("reconstructed with an empty job_id", log_reconstructed, (("job_id",), "")),
    case("reconstructed with job_id not_saved", log_reconstructed, (("job_id",), "not_saved")),
    case("reconstructed without result_rows", log_reconstructed, (("result_rows",), DELETE)),
    case("reconstructed with empty result_rows", log_reconstructed, (("result_rows",), "")),
    case("reconstructed with zero result_rows", log_reconstructed, (("result_rows",), "0")),
]


# --- structure registry row -----------------------------------------------------------------------
def reg_current() -> dict:
    return {
        "structure_id": "STR0001",
        "compound_id": "CMP0001",
        "smiles": "CCO",
        "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "connectivity_block": "LFQSCWFLJHTTHZ",
        "formula": "C2H6O",
        "net_charge": "0",
        "fragment_count": "1",
        "stereo_status": "none_present",
        "stereo_elements_specified": "0",
        "stereo_elements_total": "0",
        "standardization": "not_performed",
        "toolkit": "rdkit",
        "toolkit_version": "2026.03.4",
        "rule_version": "v0.2.0-structure-registry",
        "status": "current",
        "superseded_by": "",
        "first_seen_utc": "2026-11-09T06:00:00Z",
        "last_seen_utc": "2026-11-09T06:00:00Z",
    }


def reg_defined() -> dict:
    row = reg_current()
    row.update(
        smiles="C[C@H](N)C(=O)O",
        inchikey="QNAYBMKLOCPYGJ-REOHCLBHSA-N",
        connectivity_block="QNAYBMKLOCPYGJ",
        formula="C3H7NO2",
        stereo_status="defined",
        stereo_elements_specified="1",
        stereo_elements_total="1",
    )
    return row


def reg_partial() -> dict:
    row = reg_current()
    row.update(
        smiles="C[C@H](O)C(C)N",
        inchikey="FERWBXLFSBWTDE-BKLSDQPFSA-N",
        connectivity_block="FERWBXLFSBWTDE",
        formula="C4H11NO",
        stereo_status="partially_defined",
        stereo_elements_specified="1",
        stereo_elements_total="2",
    )
    return row


def reg_undefined() -> dict:
    row = reg_current()
    row.update(
        smiles="CC(N)C(=O)O",
        inchikey="QNAYBMKLOCPYGJ-UHFFFAOYSA-N",
        connectivity_block="QNAYBMKLOCPYGJ",
        formula="C3H7NO2",
        stereo_status="undefined",
        stereo_elements_specified="0",
        stereo_elements_total="1",
    )
    return row


def reg_superseded() -> dict:
    row = reg_current()
    row.update(status="superseded", superseded_by="STR0002", last_seen_utc="2026-11-10T08:30:00Z")
    return row


def reg_acetate() -> dict:
    row = reg_current()
    row.update(
        smiles="CC(=O)[O-]",
        inchikey="QTBSBXVTEAMEQO-UHFFFAOYSA-M",
        connectivity_block="QTBSBXVTEAMEQO",
        formula="C2H3O2-",
        net_charge="-1",
    )
    return row


def reg_salt() -> dict:
    row = reg_current()
    row.update(
        smiles="CC(=O)[O-].[Na+]",
        inchikey="VMHLLURERBWHNL-UHFFFAOYSA-M",
        connectivity_block="VMHLLURERBWHNL",
        formula="C2H3NaO2",
        fragment_count="2",
    )
    return row


REG_GOOD = [
    case("current, no stereo elements", reg_current),
    case("defined", reg_defined),
    case("partially defined", reg_partial),
    case("undefined", reg_undefined),
    case("superseded", reg_superseded),
    case("charged", reg_acetate),
    case("salt with two fragments", reg_salt),
    case("five-digit structure id", reg_current, (("structure_id",), "STR12345")),
    case(
        "five-digit superseding id",
        reg_superseded,
        (("superseded_by",), "STR12345"),
    ),
    case("short toolkit version", reg_current, (("toolkit_version",), "2026.9.1")),
    case("explicit compound id", reg_current, (("compound_id",), "ext-7")),
    case("positive charge", reg_current, (("net_charge",), "3")),
    case("two-digit charge", reg_current, (("net_charge",), "-12")),
    case("twelve fragments", reg_current, (("fragment_count",), "12")),
    case(
        "many stereo elements, all defined",
        reg_defined,
        (("stereo_elements_specified",), "12"),
        (("stereo_elements_total",), "12"),
    ),
    case(
        "first and last seen far apart", reg_current, (("last_seen_utc",), "2099-12-31T23:59:59Z")
    ),
]

TIMESTAMPS_BAD = [
    "2026-11-09",
    "2026-11-09 06:00:00Z",
    "2026-11-09T06:00:00",
    "2026-11-09T06:00:00+08:00",
    "2026-13-09T06:00:00Z",
    "2026-11-09T24:00:00Z",
    "2026-11-09T06:60:00Z",
    "2026-11-09T06:00:60Z",
    "",
    None,
]
REG_BAD_VALUES = {
    "structure_id": [
        "STR001",
        "str0001",
        "STR00x1",
        "",
        "CMP0001",
        " STR0001",
        "STR0001 ",
        1,
        None,
    ],
    "compound_id": ["", "CMP 0001", " CMP0001", 5, None],
    "smiles": ["", "CC O", " CCO", "CCO ", "CC\tO", 5, None],
    "inchikey": [
        "lfqscwfljhtthz-uhfffaoysa-n",
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-",
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-n",
        "",
        "LFQSCWFLJHTTHZUHFFFAOYSAN",
        "XLFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "LFQSCWFLJHTTH-UHFFFAOYSA-N",
        "LFQSCWFLJHTTHZ-UHFFFAOYS-N",
        5,
        None,
    ],
    "connectivity_block": [
        "LFQSCWFLJHTTH",
        "LFQSCWFLJHTTHZZ",
        "lfqscwfljhtthz",
        "",
        "LFQSCWFLJHTTHZ-",
        5,
    ],
    "formula": ["", "c2h6o", "C2 H6 O", "2C", " C2H6O", 5, None],
    "net_charge": ["+1", "01", "1.0", "", "-0", "abc", " 0", 0, None],
    "fragment_count": ["0", "", "-1", "1.5", "01", 1, None],
    "stereo_status": ["none", "Defined", "", "unknown", None],
    "stereo_elements_specified": ["-1", "", "1.0", "01", 0, None],
    "stereo_elements_total": ["-1", "", "1.0", "01", 0, None],
    "standardization": ["performed", "", "Not_Performed", None],
    "toolkit": ["openbabel", "RDKit", "", None],
    "toolkit_version": ["2026", "2026.03", "v2026.03.4", "", "2026.03.4-dev", "26.03.4", None],
    "rule_version": [
        "v0.2.0",
        "0.2.0-structure-registry",
        "v0.2.0-name-registry",
        "",
        "v0.2-structure-registry",
        None,
    ],
    "status": ["active", "Current", "", None],
    "superseded_by": ["str0002", "STR2", "CMP0002", " STR0002", None],
    "first_seen_utc": TIMESTAMPS_BAD,
    "last_seen_utc": TIMESTAMPS_BAD,
}
REG_BAD = [case(f"missing {name}", reg_current, ((name,), DELETE)) for name in REGISTRY_COLUMNS]
for _name, _values in REG_BAD_VALUES.items():
    REG_BAD += variants(_name, reg_current, (_name,), _values)
REG_BAD += [
    case("extra column", reg_current, (("note",), "x")),
    case("current with a superseded_by", reg_current, (("superseded_by",), "STR0002")),
    case("superseded without a superseded_by", reg_superseded, (("superseded_by",), "")),
    case(
        "none_present with a specified element", reg_current, (("stereo_elements_specified",), "1")
    ),
    case("none_present with a total", reg_current, (("stereo_elements_total",), "1")),
    case("defined with no elements", reg_defined, (("stereo_elements_total",), "0")),
    case("defined with none specified", reg_defined, (("stereo_elements_specified",), "0")),
    case("partially defined with one element", reg_partial, (("stereo_elements_total",), "1")),
    case(
        "partially defined with none specified", reg_partial, (("stereo_elements_specified",), "0")
    ),
    case(
        "undefined with a specified element", reg_undefined, (("stereo_elements_specified",), "1")
    ),
    case("undefined with no elements", reg_undefined, (("stereo_elements_total",), "0")),
]


# --- compound structures row ----------------------------------------------------------------------
def csr_verified() -> dict:
    return {
        "compound_id": "CMP0001",
        "group": "all",
        "name": "Ethanol",
        "stp_file": "ethanol.xlsx",
        "row_status": "accepted",
        "structure_status": "registered",
        "structure_id": "STR0001",
        "smiles": "CCO",
        "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "stereo_status": "none_present",
        "submission_status": "verified",
        "export_kind": "native_export",
        "export_sha256": EXPORT_HASH,
        "issue_codes": "",
    }


def csr_unstated() -> dict:
    row = csr_verified()
    row.update(submission_status="verified_kind_unstated", export_kind="")
    return row


def csr_reconstructed() -> dict:
    row = csr_verified()
    row.update(
        submission_status="reconstructed",
        export_kind="reconstructed_from_result_page",
        issue_codes="submission_export_reconstructed",
    )
    return row


def csr_not_recorded() -> dict:
    row = csr_verified()
    row.update(
        submission_status="not_recorded",
        export_kind="",
        export_sha256="",
        issue_codes="submission_record_missing",
    )
    return row


def csr_missing_structure() -> dict:
    row = csr_verified()
    row.update(
        row_status="quarantined",
        structure_status="not_registered",
        structure_id="",
        smiles="",
        inchikey="",
        stereo_status="",
        submission_status="not_checked",
        export_kind="",
        export_sha256="",
        issue_codes="missing_structure",
    )
    return row


def csr_rejected() -> dict:
    row = csr_verified()
    row.update(
        row_status="quarantined",
        submission_status="rejected",
        export_kind="",
        issue_codes="submission_hash_mismatch",
    )
    return row


def csr_name_only() -> dict:
    row = csr_verified()
    row.update(
        row_status="name_only",
        structure_status="name_only",
        structure_id="",
        smiles="",
        inchikey="",
        stereo_status="",
        submission_status="not_applicable",
        export_kind="",
        export_sha256="",
        issue_codes="",
    )
    return row


CSR_GOOD = [
    case("verified native export", csr_verified),
    case("verified, export kind not stated", csr_unstated),
    case("reconstructed export", csr_reconstructed),
    case("no submission record", csr_not_recorded),
    case(
        "no submission record, export hash known",
        csr_not_recorded,
        (("export_sha256",), EXPORT_HASH),
    ),
    case("missing structure", csr_missing_structure),
    case("invalid smiles", csr_missing_structure, (("issue_codes",), "invalid_smiles")),
    case("rejected submission", csr_rejected),
    case(
        "rejected because the export is missing",
        csr_rejected,
        (("export_sha256",), ""),
        (("issue_codes",), "submission_export_missing"),
    ),
    case(
        "two submission errors",
        csr_rejected,
        (("issue_codes",), "submission_hash_mismatch;submission_species_mismatch"),
    ),
    case(
        "a warning next to the error",
        csr_rejected,
        (("issue_codes",), "stereo_undefined;submission_hash_mismatch"),
    ),
    case("name-only row", csr_name_only),
    case("name-only row without an export file", csr_name_only, (("stp_file",), "")),
    case(
        "two warnings on an accepted row",
        csr_verified,
        (("issue_codes",), "charged_structure;multi_fragment"),
    ),
    case("group with a space", csr_verified, (("group",), "group A")),
    case("registered with a salt-like name", csr_verified, (("name",), "Sodium acetate (1:1)")),
    *variants("stereo status", csr_verified, ("stereo_status",), STEREO),
    *[
        case(f"warning {code}", csr_verified, (("issue_codes",), code))
        for code in FREE_ROW_WARNINGS
    ],
    *[
        case(f"error {code}", csr_missing_structure, (("issue_codes",), code))
        for code in STRUCTURE_ERRORS
    ],
    *[case(f"error {code}", csr_rejected, (("issue_codes",), code)) for code in SUBMISSION_ERRORS],
]

CSR_BAD = [case(f"missing {name}", csr_verified, ((name,), DELETE)) for name in STRUCTURES_COLUMNS]
CSR_BAD += variants("compound_id", csr_verified, ("compound_id",), ["", "CMP 0001", " CMP0001", 5])
CSR_BAD += variants("group", csr_verified, ("group",), ["", " all", "all ", "a\tb"])
CSR_BAD += variants(
    "name", csr_verified, ("name",), ["", "Eth\tanol", " Ethanol", "Ethanol ", "Eth\nanol"]
)
CSR_BAD += variants(
    "stp_file", csr_verified, ("stp_file",), [" ethanol.xlsx", "ethanol.xlsx ", "x\ny", 5]
)
CSR_BAD += variants("row_status", csr_verified, ("row_status",), ["ok", "", "Accepted", None])
CSR_BAD += variants(
    "submission_status", csr_verified, ("submission_status",), ["ok", "", "Verified", None]
)
CSR_BAD += variants(
    "export_kind", csr_verified, ("export_kind",), ["native", "Native_Export", None]
)
CSR_BAD += variants(
    "export_sha256",
    csr_verified,
    ("export_sha256",),
    [EXPORT_HASH.upper(), EXPORT_HASH[:-1], "sha256:" + EXPORT_HASH, 5, None],
)
CSR_BAD += variants("structure_id", csr_verified, ("structure_id",), ["STR1", "str0001", 1])
CSR_BAD += variants("smiles", csr_verified, ("smiles",), ["CC O", " CCO", 5])
CSR_BAD += variants(
    "inchikey",
    csr_verified,
    ("inchikey",),
    ["lfqscwfljhtthz-uhfffaoysa-n", "LFQSCWFLJHTTHZ-UHFFFAOYSA", 5],
)
CSR_BAD += variants("stereo_status", csr_verified, ("stereo_status",), ["unknown", "Defined", None])
CSR_BAD += variants(
    "issue_codes",
    csr_verified,
    ("issue_codes",),
    [
        "foo",
        "multi_fragment;",
        ";multi_fragment",
        "multi_fragment;;stereo_undefined",
        "multi_fragment; stereo_undefined",
        "Multi_Fragment",
        "multi-fragment",
        " multi_fragment",
        "log_row_without_compound",
        None,
        5,
    ],
)
CSR_BAD += [
    case("extra column", csr_verified, (("note",), "x")),
    case("accepted but not registered", csr_verified, (("structure_status",), "not_registered")),
    case("accepted but rejected", csr_verified, (("submission_status",), "rejected")),
    case("accepted but not checked", csr_verified, (("submission_status",), "not_checked")),
    case("accepted but not applicable", csr_verified, (("submission_status",), "not_applicable")),
    case("quarantined but verified", csr_rejected, (("submission_status",), "verified")),
    case(
        "quarantined, registered, not checked",
        csr_rejected,
        (("submission_status",), "not_checked"),
    ),
    case(
        "quarantined, not registered, rejected",
        csr_missing_structure,
        (("submission_status",), "rejected"),
    ),
    case(
        "quarantined with a name-only structure",
        csr_missing_structure,
        (("structure_status",), "name_only"),
    ),
    case("name-only row but registered", csr_name_only, (("structure_status",), "registered")),
    case(
        "name-only row with a submission status",
        csr_name_only,
        (("submission_status",), "not_recorded"),
    ),
    case("registered without a structure_id", csr_verified, (("structure_id",), "")),
    case("registered without smiles", csr_verified, (("smiles",), "")),
    case("registered without an inchikey", csr_verified, (("inchikey",), "")),
    case("registered without a stereo status", csr_verified, (("stereo_status",), "")),
    case(
        "not registered with a structure_id", csr_missing_structure, (("structure_id",), "STR0001")
    ),
    case("not registered with smiles", csr_missing_structure, (("smiles",), "CCO")),
    case(
        "not registered with an inchikey",
        csr_missing_structure,
        (("inchikey",), "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),
    ),
    case(
        "not registered with a stereo status",
        csr_missing_structure,
        (("stereo_status",), "undefined"),
    ),
    case("name-only with a structure_id", csr_name_only, (("structure_id",), "STR0001")),
    case("verified without an export kind", csr_verified, (("export_kind",), "")),
    case(
        "verified with the reconstructed kind",
        csr_verified,
        (("export_kind",), "reconstructed_from_result_page"),
    ),
    case("verified without an export hash", csr_verified, (("export_sha256",), "")),
    case("kind-unstated with a kind", csr_unstated, (("export_kind",), "native_export")),
    case("kind-unstated without an export hash", csr_unstated, (("export_sha256",), "")),
    case(
        "reconstructed with the native kind", csr_reconstructed, (("export_kind",), "native_export")
    ),
    case("reconstructed without a kind", csr_reconstructed, (("export_kind",), "")),
    case("reconstructed without an export hash", csr_reconstructed, (("export_sha256",), "")),
    case("not recorded with a kind", csr_not_recorded, (("export_kind",), "native_export")),
    case("rejected with a kind", csr_rejected, (("export_kind",), "native_export")),
    case("not checked with a hash", csr_missing_structure, (("export_sha256",), EXPORT_HASH)),
    case("not applicable with a hash", csr_name_only, (("export_sha256",), EXPORT_HASH)),
    case("not registered without a structure error", csr_missing_structure, (("issue_codes",), "")),
    case(
        "not registered with only a submission error",
        csr_missing_structure,
        (("issue_codes",), "submission_hash_mismatch"),
    ),
    case("rejected without an error code", csr_rejected, (("issue_codes",), "")),
    case(
        "rejected with only a structure error", csr_rejected, (("issue_codes",), "invalid_smiles")
    ),
    case("registered row with invalid_smiles", csr_verified, (("issue_codes",), "invalid_smiles")),
    case(
        "registered row with missing_structure",
        csr_verified,
        (("issue_codes",), "missing_structure"),
    ),
    case(
        "name-only row with a structure error",
        csr_name_only,
        (("issue_codes",), "missing_structure"),
    ),
    case(
        "accepted row with a submission error",
        csr_verified,
        (("issue_codes",), "submission_hash_mismatch"),
    ),
    case("not recorded without its warning", csr_not_recorded, (("issue_codes",), "")),
    case(
        "verified with the missing-record warning",
        csr_verified,
        (("issue_codes",), "submission_record_missing"),
    ),
    case("reconstructed without its warning", csr_reconstructed, (("issue_codes",), "")),
    case(
        "verified with the reconstructed warning",
        csr_verified,
        (("issue_codes",), "submission_export_reconstructed"),
    ),
]


# --- compounds audit ------------------------------------------------------------------------------
def file_ref(path: str, rows: int) -> dict:
    return {"path": path, "sha256": sha256(path), "rows": rows}


def audit_complete() -> dict:
    return {
        "schema_version": "1.0",
        "generated_by": "rnp ingest compounds",
        "stage_status": "complete",
        "identity_mode": "structure",
        "config": {"path": "run.yaml", "sha256": sha256("run.yaml")},
        "inputs": {
            "compounds": file_ref("compounds.tsv", 3),
            "submission_log": file_ref("submission_log.tsv", 3),
            "stp_dir": {"path": "stp", "files_hashed": 3},
        },
        "toolkit": {"name": "rdkit", "version": "2026.03.4"},
        "rule_versions": {
            "compound_identity": "v0.1.0-name-registry",
            "structure_identity": "v0.2.0-structure-registry",
            "submission_binding": "v0.2.0-submission-binding",
        },
        "summary": {
            "rows": 3,
            "rows_accepted": 3,
            "rows_quarantined": 0,
            "rows_name_only": 0,
            "structures_new": 3,
            "structures_reused": 0,
            "structures_superseded": 0,
            "submissions_verified": 2,
            "submissions_reconstructed": 1,
            "submissions_not_recorded": 0,
            "submissions_rejected": 0,
            "errors": 0,
            "warnings": 1,
        },
        "issues": [
            {
                "level": "warning",
                "code": "submission_export_reconstructed",
                "source": "submission_log",
                "row": 3,
                "compound_id": "CMP0003",
                "message": "export 'c.xlsx' was reconstructed from the result page",
            }
        ],
        "registries": {
            "compound_registry": {
                "path": "registry/compound_registry.tsv",
                "rule_version": "v0.1.0-name-registry",
                "entries": 3,
            },
            "structure_registry": {
                "path": "registry/structure_registry.tsv",
                "rule_version": "v0.2.0-structure-registry",
                "entries": 3,
            },
        },
        "notes": [
            {
                "code": "structure_registry_created",
                "message": "created registry/structure_registry.tsv",
            }
        ],
        "compound_structures_sha256": sha256("compound_structures.tsv"),
    }


def audit_partial() -> dict:
    doc = audit_complete()
    doc["stage_status"] = "partial"
    doc["summary"].update(
        rows_accepted=1,
        rows_quarantined=2,
        structures_new=2,
        submissions_verified=1,
        submissions_reconstructed=0,
        submissions_rejected=1,
        errors=2,
        warnings=0,
    )
    doc["issues"] = [
        {
            "level": "error",
            "code": "invalid_smiles",
            "source": "compounds",
            "row": 2,
            "compound_id": "CMP0002",
            "message": "row 2: 'C1CC' could not be parsed (unclosed ring)",
        },
        {
            "level": "error",
            "code": "submission_hash_mismatch",
            "source": "submission_log",
            "row": 3,
            "compound_id": "CMP0003",
            "message": "declared sha256 differs from the export file",
        },
    ]
    return doc


def audit_name_only() -> dict:
    doc = audit_complete()
    doc["identity_mode"] = "name_only"
    doc["toolkit"] = None
    doc["inputs"]["submission_log"] = None
    doc["inputs"]["stp_dir"] = None
    doc["rule_versions"]["structure_identity"] = None
    doc["rule_versions"]["submission_binding"] = None
    doc["registries"]["structure_registry"] = None
    doc["summary"] = {name: 0 for name in SUMMARY_FIELDS}
    doc["summary"].update(rows=3, rows_name_only=3)
    doc["issues"] = []
    return doc


def audit_no_log() -> dict:
    doc = audit_complete()
    doc["inputs"]["submission_log"] = None
    doc["rule_versions"]["submission_binding"] = None
    doc["summary"].update(
        submissions_verified=0, submissions_reconstructed=0, submissions_not_recorded=3, warnings=3
    )
    doc["issues"] = [
        {
            "level": "warning",
            "code": "submission_record_missing",
            "source": "compounds",
            "row": number,
            "compound_id": f"CMP000{number}",
            "message": f"no submission log row for compound row {number}",
        }
        for number in (1, 2, 3)
    ]
    return doc


AUDIT_GOOD = [
    case("complete, structure mode", audit_complete),
    case("partial", audit_partial),
    case("name-only mode", audit_name_only),
    case("structure mode without a submission log", audit_no_log),
    case(
        "structure mode without a log or an export directory",
        audit_no_log,
        (("inputs", "stp_dir"), None),
    ),
    case("no issues at all", audit_complete, (("issues",), []), (("summary", "warnings"), 0)),
    case("no notes", audit_complete, (("notes",), [])),
    case(
        "a later rule version",
        audit_complete,
        (("rule_versions", "structure_identity"), "v1.2.0-structure-registry"),
    ),
    case("a short toolkit version", audit_complete, (("toolkit", "version"), "2026.9.1")),
    case("empty compound id on an issue", audit_complete, (("issues", 0, "compound_id"), "")),
    case("issue about a compound row", audit_complete, (("issues", 0, "source"), "compounds")),
    case("large counts", audit_complete, (("summary", "rows"), 100000)),
    *[case(f"error code {code}", audit_partial, (("issues", 0, "code"), code)) for code in ERRORS],
    *[
        case(f"warning code {code}", audit_complete, (("issues", 0, "code"), code))
        for code in WARNINGS
    ],
]

AUDIT_BAD = [case(f"missing {name}", audit_complete, ((name,), DELETE)) for name in AUDIT_REQUIRED]
AUDIT_BAD += [
    case("extra top-level property", audit_complete, (("extra",), 1)),
    *variants("schema_version", audit_complete, ("schema_version",), ["1.1", "1.0.0", 1.0, ""]),
    *variants("generated_by", audit_complete, ("generated_by",), ["rnp ingest stp", "", None]),
    *variants("stage_status", audit_complete, ("stage_status",), ["failed", "ok", "complete ", ""]),
    *variants(
        "identity_mode", audit_complete, ("identity_mode",), ["name", "structure ", "", None]
    ),
    *variants(
        "config sha256", audit_complete, ("config", "sha256"), [sha256("x").upper(), "abc", ""]
    ),
    *variants("config path", audit_complete, ("config", "path"), ["", 5]),
    case("config without a path", audit_complete, (("config", "path"), DELETE)),
    case("config with an extra key", audit_complete, (("config", "extra"), 1)),
    *[
        case(f"inputs without {name}", audit_complete, (("inputs", name), DELETE))
        for name in ("compounds", "submission_log", "stp_dir")
    ],
    case("inputs with an extra key", audit_complete, (("inputs", "extra"), 1)),
    *variants(
        "compounds rows", audit_complete, ("inputs", "compounds", "rows"), [-1, 1.5, "3", None]
    ),
    *variants(
        "compounds sha256",
        audit_complete,
        ("inputs", "compounds", "sha256"),
        ["abc", sha256("x").upper()],
    ),
    case("compounds without a path", audit_complete, (("inputs", "compounds", "path"), DELETE)),
    case("compounds with an empty path", audit_complete, (("inputs", "compounds", "path"), "")),
    case(
        "submission log without rows",
        audit_complete,
        (("inputs", "submission_log", "rows"), DELETE),
    ),
    case(
        "export directory without a count",
        audit_complete,
        (("inputs", "stp_dir", "files_hashed"), DELETE),
    ),
    case(
        "export directory with a negative count",
        audit_complete,
        (("inputs", "stp_dir", "files_hashed"), -1),
    ),
    *variants("toolkit name", audit_complete, ("toolkit", "name"), ["openbabel", "RDKit", ""]),
    *variants(
        "toolkit version", audit_complete, ("toolkit", "version"), ["2026", "v2026.03.4", ""]
    ),
    case("toolkit without a version", audit_complete, (("toolkit", "version"), DELETE)),
    *variants(
        "structure_identity rule",
        audit_complete,
        ("rule_versions", "structure_identity"),
        ["v0.2.0-name-registry", "v0.2.0", 5],
    ),
    *variants(
        "submission_binding rule",
        audit_complete,
        ("rule_versions", "submission_binding"),
        ["v0.2.0", "v0.2.0-structure-registry", 5],
    ),
    *variants(
        "compound_identity rule", audit_complete, ("rule_versions", "compound_identity"), ["", None]
    ),
    case("rule_versions with an extra key", audit_complete, (("rule_versions", "extra"), "x")),
    *[
        case(f"summary without {name}", audit_complete, (("summary", name), DELETE))
        for name in SUMMARY_FIELDS
    ],
    case("summary with an extra field", audit_complete, (("summary", "extra"), 1)),
    *[
        case(f"negative {name}", audit_complete, (("summary", name), -1))
        for name in ("rows", "structures_new", "warnings")
    ],
    case("summary count as a string", audit_complete, (("summary", "rows"), "3")),
    *[
        case(f"issue without {name}", audit_complete, (("issues", 0, name), DELETE))
        for name in ISSUE_FIELDS
    ],
    case("issue with an extra key", audit_complete, (("issues", 0, "extra"), 1)),
    *variants("issue level", audit_complete, ("issues", 0, "level"), ["note", "Warning", "", None]),
    *variants(
        "issue code",
        audit_complete,
        ("issues", 0, "code"),
        ["other", "Missing_Structure", "missing-structure", ""],
    ),
    *variants("issue source", audit_complete, ("issues", 0, "source"), ["stp_dir", "", None]),
    *variants("issue row", audit_complete, ("issues", 0, "row"), [0, -1, "3", 1.5, None]),
    case("issue with an empty message", audit_complete, (("issues", 0, "message"), "")),
    case("issue with a non-string compound id", audit_complete, (("issues", 0, "compound_id"), 3)),
    case("error code at warning level", audit_complete, (("issues", 0, "code"), "invalid_smiles")),
    case("warning code at error level", audit_partial, (("issues", 0, "code"), "multi_fragment")),
    case(
        "log_row_without_compound at error level",
        audit_partial,
        (("issues", 0, "code"), "log_row_without_compound"),
    ),
    case("issues that is not a list", audit_complete, (("issues",), {})),
    case(
        "registries without the compound registry",
        audit_complete,
        (("registries", "compound_registry"), DELETE),
    ),
    case(
        "registries without the structure registry",
        audit_complete,
        (("registries", "structure_registry"), DELETE),
    ),
    case(
        "registry with negative entries",
        audit_complete,
        (("registries", "compound_registry", "entries"), -1),
    ),
    case(
        "registry without a rule version",
        audit_complete,
        (("registries", "structure_registry", "rule_version"), DELETE),
    ),
    case(
        "registry with an empty path",
        audit_complete,
        (("registries", "compound_registry", "path"), ""),
    ),
    case("note without a message", audit_complete, (("notes", 0, "message"), DELETE)),
    case("note with an empty message", audit_complete, (("notes", 0, "message"), "")),
    case("note with an empty code", audit_complete, (("notes", 0, "code"), "")),
    case("note with an extra key", audit_complete, (("notes", 0, "extra"), 1)),
    *variants(
        "compound_structures_sha256",
        audit_complete,
        ("compound_structures_sha256",),
        ["abc", sha256("x").upper(), "", None],
    ),
    case(
        "name-only with a toolkit",
        audit_name_only,
        (("toolkit",), {"name": "rdkit", "version": "2026.03.4"}),
    ),
    case(
        "name-only with a submission log",
        audit_name_only,
        (("inputs", "submission_log"), file_ref("l.tsv", 3)),
    ),
    case(
        "name-only with an export directory",
        audit_name_only,
        (("inputs", "stp_dir"), {"path": "stp", "files_hashed": 3}),
    ),
    case(
        "name-only with a structure rule",
        audit_name_only,
        (("rule_versions", "structure_identity"), "v0.2.0-structure-registry"),
    ),
    case(
        "name-only with a submission rule",
        audit_name_only,
        (("rule_versions", "submission_binding"), "v0.2.0-submission-binding"),
    ),
    case(
        "name-only with a structure registry",
        audit_name_only,
        (
            ("registries", "structure_registry"),
            {"path": "r.tsv", "rule_version": "v0.2.0-structure-registry", "entries": 1},
        ),
    ),
    case("name-only with accepted rows", audit_name_only, (("summary", "rows_accepted"), 1)),
    case("name-only with quarantined rows", audit_name_only, (("summary", "rows_quarantined"), 1)),
    case("name-only with new structures", audit_name_only, (("summary", "structures_new"), 1)),
    case(
        "name-only with reused structures", audit_name_only, (("summary", "structures_reused"), 1)
    ),
    case(
        "name-only with superseded structures",
        audit_name_only,
        (("summary", "structures_superseded"), 1),
    ),
    case(
        "name-only with verified submissions",
        audit_name_only,
        (("summary", "submissions_verified"), 1),
    ),
    case(
        "name-only with reconstructed submissions",
        audit_name_only,
        (("summary", "submissions_reconstructed"), 1),
    ),
    case(
        "name-only with unrecorded submissions",
        audit_name_only,
        (("summary", "submissions_not_recorded"), 1),
    ),
    case(
        "name-only with rejected submissions",
        audit_name_only,
        (("summary", "submissions_rejected"), 1),
    ),
    case("name-only with errors", audit_name_only, (("summary", "errors"), 1)),
    case("name-only but partial", audit_name_only, (("stage_status",), "partial")),
    case("structure mode without a toolkit", audit_complete, (("toolkit",), None)),
    case(
        "structure mode without a structure rule",
        audit_complete,
        (("rule_versions", "structure_identity"), None),
    ),
    case(
        "structure mode without a structure registry",
        audit_complete,
        (("registries", "structure_registry"), None),
    ),
    case("structure mode with name-only rows", audit_complete, (("summary", "rows_name_only"), 1)),
    case(
        "no log but a submission rule",
        audit_no_log,
        (("rule_versions", "submission_binding"), "v0.2.0-submission-binding"),
    ),
    case("no log but verified submissions", audit_no_log, (("summary", "submissions_verified"), 1)),
    case(
        "no log but reconstructed submissions",
        audit_no_log,
        (("summary", "submissions_reconstructed"), 1),
    ),
    case("no log but rejected submissions", audit_no_log, (("summary", "submissions_rejected"), 1)),
    case(
        "a log but no submission rule",
        audit_complete,
        (("rule_versions", "submission_binding"), None),
    ),
    case("complete with quarantined rows", audit_complete, (("summary", "rows_quarantined"), 1)),
    case("complete with errors counted", audit_complete, (("summary", "errors"), 1)),
    case(
        "complete with an error-level issue",
        audit_complete,
        (("issues", 0, "level"), "error"),
        (("issues", 0, "code"), "invalid_smiles"),
    ),
    case("partial without quarantined rows", audit_partial, (("summary", "rows_quarantined"), 0)),
    case("partial without errors counted", audit_partial, (("summary", "errors"), 0)),
    case(
        "partial without an error-level issue",
        audit_partial,
        (("issues", 0, "level"), "warning"),
        (("issues", 0, "code"), "multi_fragment"),
        (("issues", 1, "level"), "warning"),
        (("issues", 1, "code"), "multi_fragment"),
    ),
]


# --- more cases, generated per column and per rule --------------------------------------------
def affixed(valid: str) -> list[str]:
    """Strings that differ from a valid one by junk around it or in its first or last char."""
    return ["x" + valid, valid + "x", " " + valid, valid + " ", "g" + valid[1:], valid[:-1] + "g"]


def wrong_types(builder, columns, values=(5, None, ["x"])):
    return [
        case(f"{name} as {value!r}", builder, ((name,), value))
        for name in columns
        for value in values
    ]


def bogus(builder, columns):
    return [case(f"{name} __bogus__", builder, ((name,), "__bogus__")) for name in columns]


def path_label(path: tuple) -> str:
    return "/".join(str(part) for part in path)


LOG_TEXT_COLUMNS = [
    "compound",
    "structure_source",
    "result_file",
    "retrieved_date",
    "operator",
    "notes",
    "submitted_date_precision",
    "retrieved_date_basis",
    "retrieved_date_precision",
    "time_zone_windows_id",
    "utc_offset",
    "result_url",
    "job_id",
    "operator_identity",
    "submission_method",
    "submission_evidence",
]
LOG_BAD += wrong_types(log_full, LOG_COLUMNS)
LOG_BAD += bogus(log_full, ["species", "export_kind"])
LOG_BAD += [
    case(f"{name} {label}", log_full, ((name,), value))
    for name in LOG_TEXT_COLUMNS
    for label, value in (
        ("with a tab", "a\tb"),
        ("with a newline", "a\nb"),
        ("with a leading space", " a"),
        ("with a trailing space", "a "),
    )
]
for _name, _valid in (
    ("pubchem_cid", "702"),
    ("submitted_date", "2026-10-21"),
    ("result_sha256", EXPORT_HASH),
    ("result_rows", "30"),
):
    LOG_BAD += variants(f"{_name} junk", log_full, (_name,), affixed(_valid))
LOG_BAD += variants(
    "submitted_date parts",
    log_minimal,
    ("submitted_date",),
    ["2026-1a-21", "2026-10-2a", "20a6-10-21", "2026-10-40", "2026-00-21", "2026-10-00"],
)
LOG_BAD += variants("result_sha256 letters", log_full, ("result_sha256",), ["g" * 64, "A" * 64])
LOG_BAD += variants("result_rows letters", log_full, ("result_rows",), ["3a", "a3"])
LOG_GOOD += [case(f"{name} set", log_minimal, ((name,), "x")) for name in LOG_TEXT_COLUMNS]
LOG_GOOD += [
    case("latest valid date", log_minimal, (("submitted_date",), "2026-12-31")),
    case("earliest valid date", log_minimal, (("submitted_date",), "2026-01-01")),
]

REG_FIXED = (
    ("structure_id", "STR0001"),
    ("inchikey", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),
    ("connectivity_block", "LFQSCWFLJHTTHZ"),
    ("net_charge", "0"),
    ("fragment_count", "1"),
    ("stereo_elements_specified", "0"),
    ("stereo_elements_total", "0"),
    ("toolkit_version", "2026.03.4"),
    ("rule_version", "v0.2.0-structure-registry"),
    ("first_seen_utc", "2026-11-09T06:00:00Z"),
    ("last_seen_utc", "2026-11-09T06:00:00Z"),
)
TIMESTAMP_PARTS = [
    "2026-11-0aT06:00:00Z",
    "2026-1a-09T06:00:00Z",
    "20a6-11-09T06:00:00Z",
    "2026-11-09T0a:00:00Z",
    "2026-11-09T06:0a:00Z",
    "2026-11-09T06:00:0aZ",
    "2026-00-09T06:00:00Z",
    "2026-11-00T06:00:00Z",
    "2026-11-32T06:00:00Z",
    "2026-11-40T06:00:00Z",
    "2026-11-09T30:00:00Z",
    "2026-11-09T06:60:00Z",
    "2026-11-09T06:00:60Z",
    "2026-11-09T06:00:00ZZ",
]
REG_BAD += wrong_types(reg_current, REGISTRY_COLUMNS)
REG_BAD += bogus(reg_current, ["stereo_status", "status"])
for _name, _valid in REG_FIXED:
    REG_BAD += variants(f"{_name} junk", reg_current, (_name,), affixed(_valid))
REG_BAD += variants("superseded_by junk", reg_superseded, ("superseded_by",), affixed("STR0002"))
REG_BAD += variants(
    "inchikey letters",
    reg_current,
    ("inchikey",),
    [
        "LFQSCWFLJHTTHz-UHFFFAOYSA-N",
        "LFQSCWFLJHTTHZ-UHFFFAOYSa-N",
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-1",
        "1FQSCWFLJHTTHZ-UHFFFAOYSA-N",
    ],
)
REG_BAD += variants(
    "connectivity_block letters",
    reg_current,
    ("connectivity_block",),
    ["LFQSCWFLJHTThZ", "1FQSCWFLJHTTHZ"],
)
REG_BAD += variants("net_charge letters", reg_current, ("net_charge",), ["1a", "a1", "-a"])
REG_BAD += variants("fragment_count letters", reg_current, ("fragment_count",), ["1a", "a"])
REG_BAD += variants(
    "stereo_elements_total letters", reg_current, ("stereo_elements_total",), ["1a"]
)
REG_BAD += variants(
    "stereo_elements_specified letters", reg_current, ("stereo_elements_specified",), ["1a"]
)
REG_BAD += variants(
    "toolkit_version parts",
    reg_current,
    ("toolkit_version",),
    ["2026.0a.4", "2026.03.a", "20a6.03.4", "2026.003.4", "2026..4", "2026.03."],
)
REG_BAD += variants(
    "rule_version parts",
    reg_current,
    ("rule_version",),
    ["v0.a.0-structure-registry", "va.2.0-structure-registry", "v0.2.0-structure-registr"],
)
REG_BAD += variants("first_seen_utc parts", reg_current, ("first_seen_utc",), TIMESTAMP_PARTS)
REG_BAD += variants("last_seen_utc parts", reg_current, ("last_seen_utc",), TIMESTAMP_PARTS)
REG_GOOD += [
    case("earliest timestamp", reg_current, (("first_seen_utc",), "2026-01-01T00:00:00Z")),
    case("latest timestamp", reg_current, (("last_seen_utc",), "2026-12-31T23:59:59Z")),
    case("partially defined, two elements", reg_partial, (("stereo_elements_total",), "2")),
    case("partially defined, ten elements", reg_partial, (("stereo_elements_total",), "10")),
    case(
        "partially defined, twenty-five elements", reg_partial, (("stereo_elements_total",), "25")
    ),
    case("undefined, many elements", reg_undefined, (("stereo_elements_total",), "12")),
]

CSR_BAD += wrong_types(csr_verified, STRUCTURES_COLUMNS)
CSR_BAD += bogus(
    csr_verified,
    ["row_status", "structure_status", "stereo_status", "submission_status", "export_kind"],
)
CSR_BAD += variants("structure_id junk", csr_verified, ("structure_id",), affixed("STR0001"))
CSR_BAD += variants(
    "inchikey junk",
    csr_verified,
    ("inchikey",),
    affixed("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    + ["LFQSCWFLJHTTHz-UHFFFAOYSA-N", "LFQSCWFLJHTTHZ-UHFFFAOYSa-N"],
)
CSR_BAD += variants("export_sha256 junk", csr_verified, ("export_sha256",), affixed(EXPORT_HASH))
CSR_BAD += variants("smiles junk", csr_verified, ("smiles",), ["CCO\t", "C C"])
CSR_BAD += [
    case(f"accepted row with {code}", csr_verified, (("issue_codes",), code)) for code in ERRORS
]
CSR_BAD += [
    case("not checked with a kind", csr_missing_structure, (("export_kind",), "native_export")),
    case("not applicable with a kind", csr_name_only, (("export_kind",), "native_export")),
    case(
        "accepted, but the structure is not registered",
        csr_missing_structure,
        (("row_status",), "accepted"),
    ),
    case("accepted, but name-only", csr_name_only, (("row_status",), "accepted")),
    case("accepted, but the submission is rejected", csr_rejected, (("row_status",), "accepted")),
    case(
        "accepted, but the submission was not checked",
        csr_verified,
        (("submission_status",), "not_checked"),
        (("export_kind",), ""),
        (("export_sha256",), ""),
    ),
    case(
        "accepted, but the submission is not applicable",
        csr_verified,
        (("submission_status",), "not_applicable"),
        (("export_kind",), ""),
        (("export_sha256",), ""),
    ),
    case(
        "quarantined, but registered and verified", csr_verified, (("row_status",), "quarantined")
    ),
    case("quarantined, but kind-unstated", csr_unstated, (("row_status",), "quarantined")),
    case("quarantined, but reconstructed", csr_reconstructed, (("row_status",), "quarantined")),
    case("quarantined, but not recorded", csr_not_recorded, (("row_status",), "quarantined")),
    case("quarantined, but name-only", csr_name_only, (("row_status",), "quarantined")),
    case(
        "quarantined, not registered and rejected",
        csr_missing_structure,
        (("submission_status",), "rejected"),
        (("issue_codes",), "invalid_smiles;submission_hash_mismatch"),
    ),
    case(
        "quarantined, registered and not checked",
        csr_rejected,
        (("submission_status",), "not_checked"),
        (("export_sha256",), ""),
        (("issue_codes",), ""),
    ),
    case(
        "name-only, but registered",
        csr_verified,
        (("row_status",), "name_only"),
        (("submission_status",), "not_applicable"),
        (("export_kind",), ""),
        (("export_sha256",), ""),
    ),
    case("name-only, but not registered", csr_missing_structure, (("row_status",), "name_only")),
    case(
        "name-only, but with a submission status",
        csr_name_only,
        (("submission_status",), "not_recorded"),
        (("issue_codes",), "submission_record_missing"),
    ),
]

AUDIT_OBJECTS = {
    ("config",): ["path", "sha256"],
    ("inputs",): ["compounds", "submission_log", "stp_dir"],
    ("inputs", "compounds"): ["path", "sha256", "rows"],
    ("inputs", "submission_log"): ["path", "sha256", "rows"],
    ("inputs", "stp_dir"): ["path", "files_hashed"],
    ("toolkit",): ["name", "version"],
    ("rule_versions",): ["compound_identity", "structure_identity", "submission_binding"],
    ("registries",): ["compound_registry", "structure_registry"],
    ("registries", "compound_registry"): ["path", "rule_version", "entries"],
    ("registries", "structure_registry"): ["path", "rule_version", "entries"],
    ("summary",): SUMMARY_FIELDS,
    ("issues", 0): ISSUE_FIELDS,
    ("notes", 0): ["code", "message"],
}
AUDIT_STRINGS = [
    ("config", "path"),
    ("inputs", "compounds", "path"),
    ("inputs", "submission_log", "path"),
    ("inputs", "stp_dir", "path"),
    ("rule_versions", "compound_identity"),
    ("registries", "compound_registry", "path"),
    ("registries", "compound_registry", "rule_version"),
    ("registries", "structure_registry", "path"),
    ("registries", "structure_registry", "rule_version"),
    ("issues", 0, "message"),
    ("notes", 0, "code"),
    ("notes", 0, "message"),
]
AUDIT_COUNTS_FROM_ZERO = [
    ("inputs", "submission_log", "rows"),
    ("inputs", "stp_dir", "files_hashed"),
    ("registries", "compound_registry", "entries"),
    ("registries", "structure_registry", "entries"),
    *[("summary", name) for name in SUMMARY_FIELDS if name != "rows"],
]
AUDIT_COUNTS_FROM_ONE = [("inputs", "compounds", "rows"), ("summary", "rows")]
AUDIT_HASHES = [
    ("config", "sha256"),
    ("inputs", "compounds", "sha256"),
    ("inputs", "submission_log", "sha256"),
    ("compound_structures_sha256",),
]


def audit_partial_minimal() -> dict:
    doc = audit_partial()
    doc["summary"].update(rows_accepted=2, rows_quarantined=1, structures_new=3, errors=1)
    doc["summary"].update(submissions_verified=2, submissions_rejected=0)
    doc["issues"] = doc["issues"][:1]
    return doc


for _path, _keys in AUDIT_OBJECTS.items():
    AUDIT_BAD += [
        case(f"{path_label(_path)} without {key}", audit_complete, ((*_path, key), DELETE))
        for key in _keys
    ]
    AUDIT_BAD.append(
        case(f"{path_label(_path)} with an extra key", audit_complete, ((*_path, "extra"), 1))
    )
    AUDIT_BAD.append(case(f"{path_label(_path)} as a string", audit_complete, (_path, "x")))
for _path in AUDIT_STRINGS:
    AUDIT_BAD += variants(path_label(_path), audit_complete, _path, ["", 5, None])
    AUDIT_GOOD.append(case(f"{path_label(_path)} of one character", audit_complete, (_path, "x")))
for _path in AUDIT_COUNTS_FROM_ZERO + AUDIT_COUNTS_FROM_ONE:
    AUDIT_BAD += variants(path_label(_path), audit_complete, _path, [-1, 1.5, "3", None, True])
for _path in AUDIT_COUNTS_FROM_ZERO:
    AUDIT_GOOD.append(case(f"{path_label(_path)} of zero", audit_complete, (_path, 0)))
for _path in AUDIT_COUNTS_FROM_ONE:
    AUDIT_BAD.append(case(f"{path_label(_path)} of zero", audit_complete, (_path, 0)))
    AUDIT_GOOD.append(case(f"{path_label(_path)} of one", audit_complete, (_path, 1)))
for _path in AUDIT_HASHES:
    AUDIT_BAD += variants(
        path_label(_path), audit_complete, _path, affixed(sha256("x")) + ["g" * 64, 5, None]
    )
AUDIT_BAD += [
    case(f"error issue without {key}", audit_partial, (("issues", 0, key), DELETE))
    for key in ISSUE_FIELDS
]
AUDIT_BAD += [
    case("error issue with an extra key", audit_partial, (("issues", 0, "extra"), 1)),
    *variants(
        "error issue level", audit_partial, ("issues", 0, "level"), ["note", "Error", "", None]
    ),
    *variants("error issue code", audit_partial, ("issues", 0, "code"), ["__bogus__", "other", ""]),
    *variants(
        "error issue source", audit_partial, ("issues", 0, "source"), ["stp_dir", "__bogus__", None]
    ),
    *variants("error issue row", audit_partial, ("issues", 0, "row"), [0, -1, "3", 1.5, None]),
    *variants("error issue message", audit_partial, ("issues", 0, "message"), ["", 5, None]),
    *variants("error issue compound_id", audit_partial, ("issues", 0, "compound_id"), [5, None]),
    *variants("warning issue code", audit_complete, ("issues", 0, "code"), ["__bogus__"]),
    *variants("warning issue source", audit_complete, ("issues", 0, "source"), ["__bogus__"]),
    *variants("warning issue compound_id", audit_complete, ("issues", 0, "compound_id"), [5, None]),
    *bogus(audit_complete, ["stage_status", "identity_mode", "schema_version", "generated_by"]),
    *variants("toolkit name", audit_complete, ("toolkit", "name"), ["__bogus__"]),
    *variants(
        "toolkit version parts",
        audit_complete,
        ("toolkit", "version"),
        ["2026.0a.4", "2026.03.a", "20a6.03.4", "2026.003.4", "2026.03.4x", "x2026.03.4"],
    ),
    *variants(
        "structure rule parts",
        audit_complete,
        ("rule_versions", "structure_identity"),
        ["v0.a.0-structure-registry", "xv0.2.0-structure-registry", "v0.2.0-structure-registryx"],
    ),
    *variants(
        "submission rule parts",
        audit_complete,
        ("rule_versions", "submission_binding"),
        ["v0.a.0-submission-binding", "xv0.2.0-submission-binding", "v0.2.0-submission-bindingx"],
    ),
    case(
        "name-only with a submission log and its rule",
        audit_name_only,
        (("inputs", "submission_log"), file_ref("l.tsv", 3)),
        (("rule_versions", "submission_binding"), "v0.2.0-submission-binding"),
    ),
]
AUDIT_GOOD += [
    case("partial with a single quarantined row", audit_partial_minimal),
    case("empty submission log", audit_complete, (("inputs", "submission_log", "rows"), 0)),
    case(
        "a later submission rule",
        audit_complete,
        (("rule_versions", "submission_binding"), "v1.0.0-submission-binding"),
    ),
]

# --- cases that isolate one rule each ----------------------------------------------------------
CSR_BAD += [
    case(
        "accepted, not registered, with an allowed submission status",
        csr_missing_structure,
        (("row_status",), "accepted"),
        (("submission_status",), "not_recorded"),
        (("issue_codes",), "missing_structure;submission_record_missing"),
    ),
    case("stp_file with a tab", csr_verified, (("stp_file",), "a\tb")),
]
AUDIT_BAD += variants(
    "stage_status of a partial run",
    audit_partial,
    ("stage_status",),
    ["failed", "__bogus__", "Partial", ""],
)
AUDIT_BAD += variants(
    "rows_name_only in name-only mode",
    audit_name_only,
    ("summary", "rows_name_only"),
    [-1, 1.5, "3", None, True],
)
for _field in ("rows_quarantined", "errors"):
    AUDIT_BAD += variants(
        f"{_field} of a partial run",
        audit_partial,
        ("summary", _field),
        [1.5, "3", None, True, 0, -1],
    )
AUDIT_BAD += variants(
    "toolkit version more", audit_complete, ("toolkit", "version"), ["2026..4", 5, None]
)
AUDIT_GOOD += [
    case("error issue at row 1", audit_partial, (("issues", 0, "row"), 1)),
    case(
        "error issue with a one-character message", audit_partial, (("issues", 0, "message"), "x")
    ),
    case("warning issue at row 1", audit_complete, (("issues", 0, "row"), 1)),
    case("name-only run with rows", audit_name_only, (("summary", "rows_name_only"), 1)),
]

NOT_OBJECTS = [[], "row", None, 5, 1.5, True]
ALL_BAD = {
    "submission_log_row": LOG_BAD,
    "structure_registry_row": REG_BAD,
    "compound_structures_row": CSR_BAD,
    "compounds_audit": AUDIT_BAD,
}
ALL_GOOD = {
    "submission_log_row": LOG_GOOD,
    "structure_registry_row": REG_GOOD,
    "compound_structures_row": CSR_GOOD,
    "compounds_audit": AUDIT_GOOD,
}
BASELINES = [(name, builder) for name, bad in ALL_BAD.items() for builder in builders_of(bad)] + [
    (name, builder) for name, good in ALL_GOOD.items() for builder in builders_of(good)
]


# --- the tests ------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schema_is_a_well_formed_2020_12_schema(name):
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == DRAFT
    assert schema["$id"] == f"{BASE_URL}{name}.schema.json"
    assert schema["type"] == "object"
    assert isinstance(schema["title"], str) and schema["title"].strip()
    assert isinstance(schema["description"], str) and schema["description"].strip()


@pytest.mark.parametrize(
    "name, columns",
    [
        ("structure_registry_row", REGISTRY_COLUMNS),
        ("compound_structures_row", STRUCTURES_COLUMNS),
    ],
)
def test_table_schemas_list_exactly_their_columns_in_order(name, columns):
    schema = load_schema(name)
    assert list(schema["properties"]) == columns
    assert sorted(schema["required"]) == sorted(columns)
    assert schema["additionalProperties"] is False


def test_the_log_schema_names_the_existing_columns_and_the_two_new_ones():
    schema = load_schema("submission_log_row")
    assert set(schema["properties"]) == set(LOG_COLUMNS)
    assert sorted(schema["required"]) == sorted(LOG_REQUIRED)


def test_the_audit_schema_requires_its_sections():
    schema = load_schema("compounds_audit")
    assert sorted(schema["required"]) == sorted(AUDIT_REQUIRED)
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "name, builder",
    BASELINES,
    ids=[f"{name}:{builder.__name__}" for name, builder in BASELINES],
)
def test_every_baseline_is_valid(name, builder):
    assert problems(name, builder()) == []


@pytest.mark.parametrize("name", SCHEMA_NAMES)
@pytest.mark.parametrize("document", NOT_OBJECTS, ids=repr)
def test_documents_that_are_not_objects_are_rejected(name, document):
    assert not is_valid(name, document)


@pytest.mark.parametrize("builder, edits", LOG_GOOD)
def test_log_row_accepts(builder, edits):
    assert problems("submission_log_row", edited(builder, *edits)) == []


@pytest.mark.parametrize("builder, edits", LOG_BAD)
def test_log_row_rejects(builder, edits):
    assert not is_valid("submission_log_row", edited(builder, *edits))


@pytest.mark.parametrize("builder, edits", REG_GOOD)
def test_registry_row_accepts(builder, edits):
    assert problems("structure_registry_row", edited(builder, *edits)) == []


@pytest.mark.parametrize("builder, edits", REG_BAD)
def test_registry_row_rejects(builder, edits):
    assert not is_valid("structure_registry_row", edited(builder, *edits))


@pytest.mark.parametrize("builder, edits", CSR_GOOD)
def test_structures_row_accepts(builder, edits):
    assert problems("compound_structures_row", edited(builder, *edits)) == []


@pytest.mark.parametrize("builder, edits", CSR_BAD)
def test_structures_row_rejects(builder, edits):
    assert not is_valid("compound_structures_row", edited(builder, *edits))


@pytest.mark.parametrize("builder, edits", AUDIT_GOOD)
def test_audit_accepts(builder, edits):
    assert problems("compounds_audit", edited(builder, *edits)) == []


@pytest.mark.parametrize("builder, edits", AUDIT_BAD)
def test_audit_rejects(builder, edits):
    assert not is_valid("compounds_audit", edited(builder, *edits))


@pytest.mark.parametrize("code", ERRORS)
def test_each_error_code_is_refused_at_warning_level(code):
    document = edited(audit_complete, (("issues", 0, "code"), code))
    assert not is_valid("compounds_audit", document)


@pytest.mark.parametrize("code", WARNINGS)
def test_each_warning_code_is_refused_at_error_level(code):
    document = edited(audit_partial, (("issues", 0, "code"), code))
    assert not is_valid("compounds_audit", document)


def test_the_example_hash_is_the_hash_of_its_body():
    assert EXPORT_HASH == sha256(EXPORT_BODY)
    assert len(EXPORT_HASH) == 64
