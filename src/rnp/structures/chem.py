"""The only RDKit adapter of the structure library; imported lazily."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InputError

TOOLKIT = "rdkit"


class ChemUnavailable(InputError):
    """RDKit is needed but the optional ``chem`` extra is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "RDKit is not installed, so a new structure cannot be registered",
            details=[
                "install the optional extra with: uv sync --extra chem",
                "or, with an installed wheel, install it again with the extra: "
                'pip install "<path to the wheel file>[chem]"',
            ],
        )


class StructureError(Exception):
    """One SMILES string cannot be registered; this is a row problem, not a run error."""


@dataclass(frozen=True)
class StructureInfo:
    """The identifiers and counts derived from one SMILES string, without standardization."""

    smiles: str
    inchikey: str
    connectivity_block: str
    formula: str
    net_charge: int
    fragment_count: int
    stereo_status: str
    stereo_elements_specified: int
    stereo_elements_total: int


def stereo_status(specified: int, total: int) -> str:
    """Classify stereochemistry from the specified and total element counts."""
    if total == 0:
        return "none_present"
    if specified == total:
        return "defined"
    if specified == 0:
        return "undefined"
    return "partially_defined"


def toolkit_version() -> str:
    """Return the installed RDKit version, or raise :class:`ChemUnavailable`."""
    try:
        import rdkit
    except ImportError as exc:
        raise ChemUnavailable() from exc
    return rdkit.rdBase.rdkitVersion


def describe_smiles(smiles: str) -> StructureInfo:
    """Describe one SMILES string with RDKit, without changing the string."""
    if not smiles or any(character.isspace() for character in smiles):
        raise StructureError("a SMILES string must be non-empty and contain no whitespace")
    try:
        import rdkit
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors
        from rdkit.Chem.inchi import MolToInchiKey
    except ImportError as exc:
        raise ChemUnavailable() from exc

    try:
        with rdkit.rdBase.BlockLogs():
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                raise StructureError("RDKit could not parse the SMILES string")
            inchikey = MolToInchiKey(molecule)
            if not inchikey:
                raise StructureError("RDKit could not derive an InChIKey")
            formula = rdMolDescriptors.CalcMolFormula(molecule)
    except StructureError:
        raise
    except Exception as exc:
        raise StructureError(str(exc) or "RDKit could not describe the SMILES string") from exc

    fragments = len(Chem.GetMolFrags(molecule))
    elements = Chem.FindPotentialStereo(molecule)
    total = len(elements)
    specified = sum(
        1 for element in elements if element.specified == Chem.StereoSpecified.Specified
    )
    return StructureInfo(
        smiles=smiles,
        inchikey=inchikey,
        connectivity_block=inchikey.split("-")[0],
        formula=formula,
        net_charge=Chem.GetFormalCharge(molecule),
        fragment_count=fragments,
        stereo_status=stereo_status(specified, total),
        stereo_elements_specified=specified,
        stereo_elements_total=total,
    )
