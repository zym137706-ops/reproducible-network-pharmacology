"""Gene-identifier normalization (HGNC)."""

from .hgnc import GeneMapper, MapResult, map_disease_genes

__all__ = ["GeneMapper", "MapResult", "map_disease_genes"]
