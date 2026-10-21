"""Case background rule: T_r before disease, foreground T_r ∩ D."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "build_case_background.py"
HGNC = ROOT / "examples" / "demo" / "inputs" / "hgnc_map.tsv"


def _module():
    spec = importlib.util.spec_from_file_location("rnp_case_background", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _targets(path: Path, rows: list[tuple[str, str, str]]) -> None:
    lines = [
        "compound_id\tgroup\tsubmission_id\tsource_file\ttarget\tcommon_name\tuniprot_id\t"
        "target_class\tchembl_id\tprobability\tis_complex\tmulti_symbol_common_name\trow_number"
    ]
    for index, (symbol, uniprot, multi) in enumerate(rows, start=1):
        lines.append(
            f"CMP0001\tall\tS\ta.csv\tT\t{symbol}\t{uniprot}\tX\tCHEMBL1\t0.2"
            f"\tFalse\t{multi}\t{index}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_background_is_target_union_before_disease(tmp_path: Path) -> None:
    module = _module()
    main_targets = tmp_path / "targets-main.tsv"
    sens_targets = tmp_path / "targets-sens.tsv"
    _targets(
        main_targets,
        [
            ("CA2", "P00918", "false"),
            ("TNF", "P01375", "false"),
            ("CDK5R1 CDK5", "", "true"),
        ],
    )
    _targets(
        sens_targets,
        [
            ("CA2", "P00918", "false"),
            ("TNF", "P01375", "false"),
            ("ESR1", "P03372", "false"),
            ("CDK5R1 CDK5", "", "true"),
        ],
    )
    disease = tmp_path / "disease.txt"
    disease.write_text("CA2\nICAM1\n", encoding="utf-8")
    out = tmp_path / "backgrounds"
    assert module.main(
        [
            "--targets",
            f"main={main_targets}",
            "--targets",
            f"sens={sens_targets}",
            "--disease-genes",
            str(disease),
            "--hgnc-map",
            str(HGNC),
            "--out-dir",
            str(out),
        ]
    ) == 0

    main = (out / "universe-main.txt").read_text(encoding="utf-8").split()
    sens = (out / "universe-sens.txt").read_text(encoding="utf-8").split()
    assert main == ["CA2", "TNF"]
    assert sens == ["CA2", "ESR1", "TNF"]
    assert (out / "foreground-main.txt").read_text(encoding="utf-8").split() == ["CA2"]
    assert (out / "foreground-sens.txt").read_text(encoding="utf-8").split() == ["CA2"]
    meta = json.loads((out / "background-sens.meta.json").read_text(encoding="utf-8"))
    assert meta["conditional_within_predicted_targets"] is True
    assert meta["background_size"] == 3
    assert meta["foreground_size"] == 1
    assert meta["target_counts"]["skipped_multi"] >= 1
    assert meta["background_sha256"] == __import__("hashlib").sha256(
        (out / "universe-sens.txt").read_bytes()
    ).hexdigest()
