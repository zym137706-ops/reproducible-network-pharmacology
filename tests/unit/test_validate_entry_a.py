"""`rnp validate` checks the submission log when the config names one."""

from __future__ import annotations

import json

from compounds_support import (
    NAME_COLUMNS,
    compound_row,
    six_compounds,
    six_log,
    write_config,
    write_exports,
)

from rnp.cli import main


def test_a_config_without_a_submission_log_validates_as_before(tmp_path, capsys):
    write_exports(tmp_path)
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    assert main(["validate", "--config", str(config)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert "submission_log" not in payload


def test_an_existing_submission_log_is_reported(tmp_path, capsys):
    digests = write_exports(tmp_path)
    config = write_config(tmp_path, six_compounds(), log_rows=six_log(digests))
    assert main(["validate", "--config", str(config)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["submission_log"] == str(tmp_path / "inputs" / "log.tsv")


def test_a_missing_submission_log_is_an_input_error(tmp_path, capsys):
    write_exports(tmp_path)
    config = write_config(
        tmp_path, six_compounds(), inputs={"submission_log": str(tmp_path / "nowhere.tsv")}
    )
    assert main(["validate", "--config", str(config)]) == 2
    error = capsys.readouterr().err
    assert "inputs.submission_log" in error and "not a file" in error


def test_a_structure_registry_does_not_have_to_exist(tmp_path, capsys):
    write_exports(tmp_path)
    config = write_config(
        tmp_path, six_compounds(), inputs={"structure_registry": str(tmp_path / "later.tsv")}
    )
    assert main(["validate", "--config", str(config)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert not (tmp_path / "later.tsv").exists()
