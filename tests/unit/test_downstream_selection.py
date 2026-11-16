"""`rnp intersect` and `rnp network` after `ingest stp --selection`.

When `compounds_registered.tsv` has the column `selection_status`, the two commands count and list
only the selected compounds: a compound that the researcher excluded is no candidate of the analysis
any more, so it is neither a compound of its group nor a compound "without edges" (which reads like
a failed prediction). Without the column (no `--selection`) nothing changes. Selecting everything
gives the results of selecting nothing explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from selection_ingest_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    FOUR_OK,
    decision,
    downstream,
    ingest,
    make,
    read_json,
    read_tsv,
)

from rnp.analysis.intersect import run_intersect
from rnp.config import load_config
from rnp.errors import InputError

TWO_GROUPS = ["g1", "g1", "g2", "g2"]
G2_EXCLUDED = [
    decision("Compound 1", "include", group="g1"),
    decision("Compound 2", "include", group="g1"),
    decision("Compound 3", "exclude", group="g2", reason="out_of_scope"),
    decision("Compound 4", "exclude", group="g2", reason="out_of_scope"),
]
ALL_INCLUDED = [
    decision(f"Compound {n}", "include", group=group) for n, group in enumerate(TWO_GROUPS, start=1)
]


def stats(audit, group, *names):
    return tuple(audit["groups"][group][name] for name in names)


# --- intersect ------------------------------------------------------------------------------------
def test_intersect_counts_only_the_selected_compounds(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case)["run_dir"])
    audit = downstream(case, run_dir)["intersect"]
    assert sorted(audit["groups"]) == ["all"]
    assert stats(
        audit, "all", "compounds", "compounds_linked", "edges", "targets", "intersection"
    ) == (
        2,
        1,
        2,
        2,
        1,
    )
    assert audit["groups"]["all"]["compounds_without_edges"] == ["Compound 4"]


def test_without_the_selection_every_registered_compound_is_counted(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case, selection=None)["run_dir"])
    audit = downstream(case, run_dir, allow_partial=True)["intersect"]
    assert stats(audit, "all", "compounds", "compounds_linked") == (4, 1)
    assert audit["groups"]["all"]["compounds_without_edges"] == [
        "Compound 2",
        "Compound 3",
        "Compound 4",
    ]


def test_a_group_without_a_selected_compound_is_not_listed(tmp_path):
    case = make(tmp_path, G2_EXCLUDED, FOUR_OK, groups=TWO_GROUPS)
    run_dir = Path(ingest(case)["run_dir"])
    result = downstream(case, run_dir)
    audit = result["intersect"]
    assert sorted(audit["groups"]) == ["g1"]
    assert stats(
        audit, "g1", "compounds", "compounds_linked", "edges", "targets", "intersection"
    ) == (
        2,
        2,
        3,
        3,
        2,
    )
    assert sorted(read_json(run_dir / "intersect" / "venn.json")["groups"]) == ["g1"]
    assert sorted(result["network"]["groups"]) == ["g1"]
    assert not (run_dir / "network" / "g2").exists()


def test_without_the_selection_both_groups_are_listed(tmp_path):
    case = make(tmp_path, G2_EXCLUDED, FOUR_OK, groups=TWO_GROUPS)
    run_dir = Path(ingest(case, selection=None)["run_dir"])
    result = downstream(case, run_dir)
    audit = result["intersect"]
    assert sorted(audit["groups"]) == ["g1", "g2"]
    assert stats(audit, "g2", "compounds", "compounds_linked", "edges", "intersection") == (
        2,
        1,
        2,
        1,
    )
    assert audit["groups"]["g2"]["compounds_without_edges"] == ["Compound 4"]
    assert sorted(result["network"]["groups"]) == ["g1", "g2"]


def test_a_partial_selection_needs_the_override_downstream(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    summary = ingest(case)
    assert summary["stage_status"] == "partial"
    run_dir = Path(summary["run_dir"])
    config = load_config(case.config)
    with pytest.raises(InputError) as caught:
        run_intersect(config, run_dir / "targets.tsv", run_dir / "intersect")
    assert "not 'complete'" in caught.value.message
    assert not (run_dir / "intersect").exists()
    audit = downstream(case, run_dir, allow_partial=True)["intersect"]
    assert "upstream_status_override" in {item["code"] for item in audit["warnings"]}
    assert stats(audit, "all", "compounds", "compounds_linked") == (1, 1)
    assert audit["groups"]["all"]["compounds_without_edges"] == []


# --- network --------------------------------------------------------------------------------------
def test_network_lists_only_the_selected_compounds(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case)["run_dir"])
    result = downstream(case, run_dir)
    group = result["network"]["groups"]["all"]
    assert (group["compounds_total"], group["compounds_linked"], group["targets"]) == (2, 1, 1)
    rows = read_tsv(run_dir / "network" / "all" / "mol_list.tsv")
    assert [(row["MOLID"], row["moleculename"]) for row in rows] == [
        ("MOL0001", "Compound 1"),
        ("MOL0002", "Compound 4"),
    ]


def test_without_the_selection_network_lists_every_registered_compound(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    run_dir = Path(ingest(case, selection=None)["run_dir"])
    result = downstream(case, run_dir, allow_partial=True)
    assert result["network"]["groups"]["all"]["compounds_total"] == 4
    rows = read_tsv(run_dir / "network" / "all" / "mol_list.tsv")
    assert [row["moleculename"] for row in rows] == [f"Compound {n}" for n in range(1, 5)]


def test_the_name_of_an_excluded_compound_may_be_a_gene_symbol(tmp_path):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "include"),
        decision("Compound 3", "exclude", reason="out_of_scope"),
    ]
    case = make(tmp_path, rows, mode="name", names=3, renames={"Compound 3": "TNF"})
    chosen = Path(ingest(case)["run_dir"])
    result = downstream(case, chosen)
    assert result["network"]["groups"]["all"]["compounds_total"] == 2
    plain = Path(ingest(case, run_id="plain", selection=None)["run_dir"])
    with pytest.raises(InputError) as caught:
        downstream(case, plain)
    assert caught.value.message == (
        "compound names collide with gene symbols; Cytoscape nodes would merge"
    )


# --- selecting everything -------------------------------------------------------------------------
INTERSECT_FILES = [
    "disease_genes.tsv",
    "edges.tsv",
    "gene_mapping_conflicts.tsv",
    "intersection_genes.tsv",
    "target_exclusions.tsv",
    "venn.json",
]


def test_selecting_everything_gives_the_results_of_no_selection(tmp_path):
    case = make(tmp_path, ALL_INCLUDED, FOUR_OK, groups=TWO_GROUPS)
    plain = Path(ingest(case, run_id="plain", selection=None)["run_dir"])
    chosen = Path(ingest(case, run_id="chosen")["run_dir"])
    plain_result = downstream(case, plain)
    chosen_result = downstream(case, chosen)
    assert plain_result["intersect"]["groups"] == chosen_result["intersect"]["groups"]
    for name in INTERSECT_FILES:
        assert (plain / "intersect" / name).read_bytes() == (
            chosen / "intersect" / name
        ).read_bytes()
    assert plain_result["network"]["groups"].keys() == chosen_result["network"]["groups"].keys()
    for group in plain_result["network"]["groups"]:
        for name in ("edges.tsv", "nodes.tsv", "mol_list.tsv", "node_attributes.tsv"):
            left = (plain / "network" / group / name).read_bytes()
            assert left == (chosen / "network" / group / name).read_bytes(), (group, name)
    assert (plain / "targets.tsv").read_bytes() == (chosen / "targets.tsv").read_bytes()
