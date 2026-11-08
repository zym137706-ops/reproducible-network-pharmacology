"""Endpoints, identifiers and request building for the acquisition step (ADR-0005).

Pure constants and functions: nothing here uses the network or reads a clock.
"""

from __future__ import annotations

import json
import re

from .transport import DEFAULT_TIMEOUT, FetchRequest

ROLE_MMCIF = "structure_mmcif"
ROLE_ENTRY = "rcsb_entry"
ROLE_GRAPHQL = "rcsb_graphql"
ROLE_UNIPROT = "uniprot_entry"
ROLES = (ROLE_MMCIF, ROLE_ENTRY, ROLE_GRAPHQL, ROLE_UNIPROT)

PDB_ID_REGEX = r"^[0-9][A-Z0-9]{3}$"
UNIPROT_ACCESSION_REGEX = (
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

MMCIF_URL = "https://files.rcsb.org/download/{key}.cif"
ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{key}"
GRAPHQL_URL = "https://data.rcsb.org/graphql"
UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/{key}.json"

HEADER_WHITELIST = (
    "date",
    "last-modified",
    "etag",
    "x-uniprot-release",
    "x-uniprot-release-date",
    "x-api-deployment-date",
)

GRAPHQL_QUERY = (
    "query($ids:[String!]!){ entries(entry_ids:$ids){ rcsb_id struct{ title } exptl{ method } "
    "rcsb_entry_info{ resolution_combined polymer_entity_count nonpolymer_entity_count } "
    "rcsb_accession_info{ initial_release_date revision_date } polymer_entities{ "
    "rcsb_polymer_entity_container_identifiers{ entity_id auth_asym_ids asym_ids "
    "reference_sequence_identifiers{ database_name database_accession database_isoform "
    "entity_sequence_coverage reference_sequence_coverage } } "
    "rcsb_polymer_entity{ pdbx_description } entity_poly{ rcsb_entity_polymer_type "
    "pdbx_seq_one_letter_code_can rcsb_mutation_count rcsb_sample_sequence_length } "
    "rcsb_polymer_entity_align{ reference_database_name reference_database_accession "
    "provenance_source aligned_regions{ entity_beg_seq_id ref_beg_seq_id length } } "
    "rcsb_entity_source_organism{ ncbi_taxonomy_id ncbi_scientific_name } "
    "polymer_entity_instances{ rcsb_polymer_entity_instance_container_identifiers{ entity_id "
    "auth_asym_id asym_id auth_to_entity_poly_seq_mapping } } } "
    "nonpolymer_entities{ pdbx_entity_nonpoly{ comp_id name } "
    "rcsb_nonpolymer_entity_container_identifiers{ entity_id auth_asym_ids asym_ids "
    "nonpolymer_comp_id } } assemblies{ rcsb_id pdbx_struct_assembly{ id oligomeric_details "
    "oligomeric_count } } } }"
)


def is_pdb_id(value) -> bool:
    """True for a string that is exactly a four-character PDB ID."""
    return isinstance(value, str) and re.fullmatch(PDB_ID_REGEX, value) is not None


def is_uniprot_accession(value) -> bool:
    """True for a string that is exactly a canonical UniProt accession."""
    return isinstance(value, str) and re.fullmatch(UNIPROT_ACCESSION_REGEX, value) is not None


def graphql_body(pdb_id: str) -> bytes:
    """The canonical JSON POST body that asks about one PDB ID."""
    document = {"query": GRAPHQL_QUERY, "variables": {"ids": [pdb_id]}}
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def build_request(role: str, key: str, timeout: float = DEFAULT_TIMEOUT) -> FetchRequest:
    """Build the request for one role and key; nothing is sent here."""
    if role == ROLE_MMCIF:
        return FetchRequest("GET", MMCIF_URL.format(key=key), {}, None, timeout)
    if role == ROLE_ENTRY:
        return FetchRequest(
            "GET", ENTRY_URL.format(key=key), {"Accept": "application/json"}, None, timeout
        )
    if role == ROLE_GRAPHQL:
        return FetchRequest(
            "POST",
            GRAPHQL_URL,
            {"Accept": "application/json", "Content-Type": "application/json"},
            graphql_body(key),
            timeout,
        )
    if role == ROLE_UNIPROT:
        return FetchRequest(
            "GET", UNIPROT_URL.format(key=key), {"Accept": "application/json"}, None, timeout
        )
    raise ValueError(f"unknown acquisition role: {role!r}")
