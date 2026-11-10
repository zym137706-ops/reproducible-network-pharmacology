"""Strict reading of the tab-separated tables (rnp.structures.tables)."""

from __future__ import annotations

import pytest
from structures_support import write_text

from rnp.errors import InputError
from rnp.structures.tables import read_rows


def test_header_and_rows_are_returned_as_raw_strings(tmp_path):
    path = write_text(tmp_path / "t.tsv", "a\tb\tc\n1\t x \t3\n4\t5\t6\n")
    header, rows = read_rows(path)
    assert header == ["a", "b", "c"]
    assert rows == [{"a": "1", "b": " x ", "c": "3"}, {"a": "4", "b": "5", "c": "6"}]


def test_a_bom_and_crlf_are_accepted(tmp_path):
    path = tmp_path / "t.tsv"
    path.write_bytes((chr(0xFEFF) + "a\tb\r\n1\t2\r\n").encode("utf-8"))
    assert read_rows(path) == (["a", "b"], [{"a": "1", "b": "2"}])


def test_blank_rows_are_skipped(tmp_path):
    path = write_text(tmp_path / "t.tsv", "a\tb\n\n1\t2\n \t \n\n3\t4\n")
    assert read_rows(path)[1] == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_a_header_with_no_rows(tmp_path):
    assert read_rows(write_text(tmp_path / "t.tsv", "a\tb\n")) == (["a", "b"], [])


def test_short_rows_are_padded(tmp_path):
    path = write_text(tmp_path / "t.tsv", "a\tb\tc\n1\n")
    assert read_rows(path)[1] == [{"a": "1", "b": "", "c": ""}]


def test_a_comma_separated_table_is_read_too(tmp_path):
    path = write_text(tmp_path / "t.csv", "a,b\n1,2\n")
    assert read_rows(path) == (["a", "b"], [{"a": "1", "b": "2"}])


def test_quoted_cells_may_contain_the_delimiter(tmp_path):
    path = write_text(tmp_path / "t.tsv", 'a\tb\n"x\ty"\t2\n')
    assert read_rows(path)[1] == [{"a": "x\ty", "b": "2"}]


def test_a_row_with_too_many_cells_is_refused_with_its_number(tmp_path):
    path = write_text(tmp_path / "t.tsv", "a\tb\n1\t2\n\n3\t4\t5\n6\t7\t8\t9\n")
    with pytest.raises(InputError) as caught:
        read_rows(path)
    assert caught.value.exit_code == 2
    assert [d.split(":")[0] for d in caught.value.details] == ["row 2", "row 3"]
    assert "t.tsv" in caught.value.message


@pytest.mark.parametrize("text", ["", "\n", " \t \n1\t2\n"])
def test_a_table_without_a_header_is_refused(tmp_path, text):
    with pytest.raises(InputError):
        read_rows(write_text(tmp_path / "t.tsv", text))


def test_a_repeated_column_name_is_refused(tmp_path):
    with pytest.raises(InputError):
        read_rows(write_text(tmp_path / "t.tsv", "a\ta\n1\t2\n"))


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(InputError):
        read_rows(tmp_path / "nowhere.tsv")


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    path = tmp_path / "t.tsv"
    path.write_bytes(b"a\tb\n\xff\xfe\t2\n")
    with pytest.raises(InputError):
        read_rows(path)
