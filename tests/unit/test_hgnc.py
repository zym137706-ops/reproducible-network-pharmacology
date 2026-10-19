"""HGNC mapping rules: every ambiguity path has a test."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnp.errors import InputError
from rnp.normalize.hgnc import GeneMapper, map_disease_genes


@pytest.fixture
def mapper(fixtures: Path) -> GeneMapper:
    return GeneMapper(fixtures / "hgnc" / "hgnc_map.tsv")


def test_approved_symbol(mapper: GeneMapper) -> None:
    result = mapper.map("CA2")
    assert result.gene_symbol == "CA2"
    assert result.mapping_status == "approved_symbol"
    assert result.entrez_id == "760"
    assert result.mapping_conflict is False


def test_symbol_is_case_insensitive(mapper: GeneMapper) -> None:
    assert mapper.map("ca2").gene_symbol == "CA2"


def test_alias_and_previous_symbols(mapper: GeneMapper) -> None:
    alias = mapper.map("COX2")
    assert (alias.gene_symbol, alias.mapping_status) == ("PTGS2", "alias_symbol")
    previous = mapper.map("IL8")
    assert (previous.gene_symbol, previous.mapping_status) == ("CXCL8", "previous_symbol")


def test_unique_uniprot_resolves_missing_symbol(mapper: GeneMapper) -> None:
    result = mapper.map("", "P00918")
    assert (result.gene_symbol, result.mapping_status) == ("CA2", "unique_UniProt")


def test_ambiguous_alias_is_not_guessed(mapper: GeneMapper) -> None:
    result = mapper.map("ERK")
    assert result.gene_symbol == ""
    assert result.mapping_status == "unmapped"
    assert result.ambiguous_symbols == "MAPK1;MAPK3"


def test_symbol_uniprot_conflict_is_flagged(mapper: GeneMapper) -> None:
    result = mapper.map("TNF", "P05231")  # P05231 is IL6
    assert result.gene_symbol == "TNF"
    assert result.mapping_conflict is True
    assert "symbol_UniProt_conflict" in result.mapping_status


def test_retired_records_are_ignored(mapper: GeneMapper) -> None:
    assert mapper.map("RETIREDGENE").gene_symbol == ""


def test_placeholders_are_unmapped(mapper: GeneMapper) -> None:
    assert mapper.map("N/A").gene_symbol == ""
    assert mapper.map("-").gene_symbol == ""


def test_disease_genes_are_mapped_and_deduplicated(
    fixtures: Path, mapper: GeneMapper
) -> None:
    audit = map_disease_genes(fixtures / "run" / "inputs" / "disease_genes.txt", mapper)
    genes = [row["gene_symbol"] for row in audit]
    assert len(genes) == 10
    assert len(set(genes)) == 10


def test_unresolved_disease_gene_raises(tmp_path: Path, mapper: GeneMapper) -> None:
    path = tmp_path / "disease.txt"
    path.write_text("TNF\nNOSUCHGENE\n", encoding="utf-8")
    with pytest.raises(InputError) as excinfo:
        map_disease_genes(path, mapper)
    assert "NOSUCHGENE" in excinfo.value.render()


def test_missing_columns_raise(tmp_path: Path) -> None:
    path = tmp_path / "hgnc.tsv"
    path.write_text("hgnc_id\tsymbol\nHGNC:1\tA\n", encoding="utf-8")
    with pytest.raises(InputError):
        GeneMapper(path)
