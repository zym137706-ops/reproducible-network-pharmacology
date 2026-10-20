"""PubChem structure fetch: current fields, CID checks and no empty success."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "fetch_pubchem_structures.py"


def _module():
    spec = importlib.util.spec_from_file_location("rnp_pubchem_fetch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(cid: str = "5280343", **fields):
    record = {"CID": int(cid)}
    record.update(fields)
    return {"PropertyTable": {"Properties": [record]}}


def test_current_fields_are_parsed() -> None:
    module = _module()
    parsed = module._parse_properties(
        _payload(
            SMILES="C1=CC=C(C=C1)O",
            ConnectivitySMILES="C1=CC=C(C=C1)O",
        ),
        "5280343",
    )
    assert parsed == {
        "pubchem_cid": "5280343",
        "smiles": "C1=CC=C(C=C1)O",
        "connectivity_smiles": "C1=CC=C(C=C1)O",
    }


def test_old_field_names_are_not_silently_accepted() -> None:
    module = _module()
    payload = _payload(CanonicalSMILES="CCO", IsomericSMILES="CCO")
    with pytest.raises(module.PubChemError, match="SMILES"):
        module._parse_properties(payload, "5280343")


def test_missing_connectivity_smiles_fails() -> None:
    module = _module()
    payload = _payload(SMILES="CCO")
    with pytest.raises(module.PubChemError, match="ConnectivitySMILES"):
        module._parse_properties(payload, "5280343")


def test_empty_structure_fails() -> None:
    module = _module()
    payload = _payload(SMILES="   ", ConnectivitySMILES="CCO")
    with pytest.raises(module.PubChemError, match="SMILES"):
        module._parse_properties(payload, "5280343")


def test_cid_mismatch_fails() -> None:
    module = _module()
    payload = _payload("999", SMILES="CCO", ConnectivitySMILES="CCO")
    with pytest.raises(module.PubChemError, match="CID mismatch"):
        module._parse_properties(payload, "5280343")


def test_failed_fetch_does_not_write_a_success_table(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    compounds = tmp_path / "compounds.tsv"
    compounds.write_text("name\tpubchem_cid\nQuercetin\t5280343\n", encoding="utf-8")
    out = tmp_path / "out"

    def fail(_cid: str):
        raise module.PubChemError("forced response failure")

    monkeypatch.setattr(module, "_fetch_payload", fail)
    code = module.main(["--compounds", str(compounds), "--out", str(out)])
    assert code == 2
    assert not (out / "pubchem_structures.tsv").exists()
