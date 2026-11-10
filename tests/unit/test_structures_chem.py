"""The RDKit adapter of rnp.structures: what a SMILES string becomes, and when RDKit is needed.

Tests that need RDKit use the `chem` fixture: without RDKit they are skipped, unless the environment
variable RNP_REQUIRE_CHEM is 1 (CI sets it), in which case a missing RDKit is a failure, not a skip.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

from rnp.errors import InputError
from rnp.structures import (
    ChemUnavailable,
    StructureError,
    StructureInfo,
    describe_smiles,
    toolkit_version,
)
from rnp.structures import chem as chem_module


@pytest.fixture
def chem():
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


# smiles -> (inchikey, formula, net_charge, fragments, stereo_status, specified, total)
KNOWN = {
    "CCO": ("LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "C2H6O", 0, 1, "none_present", 0, 0),
    "c1ccccc1": ("UHOVQNZJYSORNB-UHFFFAOYSA-N", "C6H6", 0, 1, "none_present", 0, 0),
    "C[C@H](N)C(=O)O": ("QNAYBMKLOCPYGJ-REOHCLBHSA-N", "C3H7NO2", 0, 1, "defined", 1, 1),
    "C[C@@H](N)C(=O)O": ("QNAYBMKLOCPYGJ-UWTATZPHSA-N", "C3H7NO2", 0, 1, "defined", 1, 1),
    "CC(N)C(=O)O": ("QNAYBMKLOCPYGJ-UHFFFAOYSA-N", "C3H7NO2", 0, 1, "undefined", 0, 1),
    "C[C@H](O)C(C)N": ("FERWBXLFSBWTDE-BKLSDQPFSA-N", "C4H11NO", 0, 1, "partially_defined", 1, 2),
    "C[C@H](O)[C@@H](C)N": ("FERWBXLFSBWTDE-DMTCNVIQSA-N", "C4H11NO", 0, 1, "defined", 2, 2),
    "CC(=O)[O-].[Na+]": ("VMHLLURERBWHNL-UHFFFAOYSA-M", "C2H3NaO2", 0, 2, "none_present", 0, 0),
    "CC(=O)[O-]": ("QTBSBXVTEAMEQO-UHFFFAOYSA-M", "C2H3O2-", -1, 1, "none_present", 0, 0),
    "C[N+](C)(C)C": ("QEMXHQIAXOOASZ-UHFFFAOYSA-N", "C4H12N+", 1, 1, "none_present", 0, 0),
    "[NH4+].[Cl-]": ("NLXLAEXVIDQMFP-UHFFFAOYSA-N", "H4ClN", 0, 2, "none_present", 0, 0),
    "C/C=C/C": ("IAQRGUVFOMOMEM-ONEGZZNKSA-N", "C4H8", 0, 1, "defined", 1, 1),
    "C/C=C\\C": ("IAQRGUVFOMOMEM-ARJAWSKDSA-N", "C4H8", 0, 1, "defined", 1, 1),
    "CC=CC": ("IAQRGUVFOMOMEM-UHFFFAOYSA-N", "C4H8", 0, 1, "undefined", 0, 1),
    "C1=CC(=C(C=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O)O": (
        "REFJWTPEDVJJIY-UHFFFAOYSA-N",
        "C15H10O7",
        0,
        1,
        "none_present",
        0,
        0,
    ),
    "O": ("XLYOFNOQVPJJNP-UHFFFAOYSA-N", "H2O", 0, 1, "none_present", 0, 0),
}
NOT_STRUCTURES = [
    "",
    " ",
    "CC O",
    "\tCCO",
    "CCO\n",
    "not a smiles",
    "C1CC",
    "[Xx]",
    "C(C)(C)(C)(C)C",
    "CCO.",
    "C=",
    "()",
    "*CC",
    "[*]",
]


@pytest.mark.parametrize("smiles", sorted(KNOWN))
def test_describe_smiles_derives_the_documented_fields(chem, smiles):
    key, formula, charge, fragments, status, specified, total = KNOWN[smiles]
    info = describe_smiles(smiles)
    assert isinstance(info, StructureInfo)
    assert info.smiles == smiles
    assert info.inchikey == key
    assert info.connectivity_block == key.split("-")[0]
    assert info.formula == formula
    assert info.net_charge == charge
    assert info.fragment_count == fragments
    assert info.stereo_status == status
    assert info.stereo_elements_specified == specified
    assert info.stereo_elements_total == total


@pytest.mark.parametrize("smiles", sorted(KNOWN))
def test_describe_smiles_values_have_the_registry_formats(chem, smiles):
    info = describe_smiles(smiles)
    assert re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", info.inchikey)
    assert re.fullmatch(r"[A-Z]{14}", info.connectivity_block)
    assert isinstance(info.net_charge, int) and not isinstance(info.net_charge, bool)
    assert isinstance(info.fragment_count, int) and info.fragment_count >= 1
    assert 0 <= info.stereo_elements_specified <= info.stereo_elements_total


@pytest.mark.parametrize("smiles", NOT_STRUCTURES)
def test_describe_smiles_refuses_what_is_not_a_structure(chem, smiles):
    with pytest.raises(StructureError) as caught:
        describe_smiles(smiles)
    assert str(caught.value)


def test_a_structure_error_is_a_row_problem_not_a_run_error(chem):
    assert not issubclass(StructureError, InputError)
    with pytest.raises(StructureError):
        describe_smiles("C1CC")


def test_describe_smiles_does_not_standardize(chem):
    salt = describe_smiles("CC(=O)[O-].[Na+]")
    assert salt.fragment_count == 2 and salt.net_charge == 0 and salt.smiles == "CC(=O)[O-].[Na+]"
    acetate = describe_smiles("CC(=O)[O-]")
    assert acetate.net_charge == -1


def test_stereo_is_not_invented_and_not_dropped(chem):
    assert describe_smiles("CC(N)C(=O)O").stereo_status == "undefined"
    assert describe_smiles("C[C@H](N)C(=O)O").stereo_status == "defined"
    assert describe_smiles("C[C@H](O)C(C)N").stereo_status == "partially_defined"
    assert describe_smiles("CC=CC").stereo_status == "undefined"
    assert describe_smiles("C/C=C/C").stereo_status == "defined"
    assert describe_smiles("CCO").stereo_status == "none_present"


def test_different_stereo_gives_a_different_key_with_the_same_connectivity(chem):
    left = describe_smiles("C[C@H](N)C(=O)O")
    right = describe_smiles("C[C@@H](N)C(=O)O")
    assert left.inchikey != right.inchikey
    assert left.connectivity_block == right.connectivity_block


def test_describe_smiles_is_quiet_about_bad_input(chem, capfd):
    with pytest.raises(StructureError):
        describe_smiles("C1CC")
    assert capfd.readouterr().err == ""


def test_toolkit_version_is_the_installed_rdkit_version(chem):
    import rdkit

    version = toolkit_version()
    assert version == rdkit.rdBase.rdkitVersion
    assert re.fullmatch(r"[0-9]{4}\.[0-9]{1,2}\.[0-9]+", version)


@pytest.mark.parametrize(
    "specified, total, status",
    [
        (0, 0, "none_present"),
        (1, 1, "defined"),
        (3, 3, "defined"),
        (0, 1, "undefined"),
        (0, 4, "undefined"),
        (1, 2, "partially_defined"),
        (3, 4, "partially_defined"),
    ],
)
def test_stereo_status_from_the_two_counts(specified, total, status):
    assert chem_module.stereo_status(specified, total) == status


# --- what happens without RDKit -------------------------------------------------------------------
@pytest.fixture
def no_rdkit(monkeypatch):
    """Make `import rdkit` fail, whether or not RDKit is installed."""
    monkeypatch.setitem(sys.modules, "rdkit", None)


def test_without_rdkit_describing_a_structure_is_a_clear_run_error(no_rdkit):
    with pytest.raises(ChemUnavailable) as caught:
        describe_smiles("CCO")
    assert isinstance(caught.value, InputError)
    assert caught.value.exit_code == 2
    rendered = caught.value.render()
    assert "RDKit" in rendered and "chem" in rendered


def test_without_rdkit_the_toolkit_version_is_a_clear_run_error(no_rdkit):
    with pytest.raises(ChemUnavailable):
        toolkit_version()


@pytest.mark.parametrize("smiles", ["", " ", "CC O", "\tCCO"])
def test_without_rdkit_an_unusable_string_is_still_a_row_problem(no_rdkit, smiles):
    with pytest.raises(StructureError):
        describe_smiles(smiles)


def test_importing_the_package_does_not_import_rdkit():
    code = "import sys; import rnp.structures; print('rdkit' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ),
    )
    assert result.stdout.strip() == "False"
