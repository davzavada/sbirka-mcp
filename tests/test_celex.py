"""Offline tests for EU case-law identifier parsing (no network)."""

import pytest

from curia_mcp.celex import (
    is_celex,
    parse_case_number,
    parse_celex,
    parse_ecli,
)
from curia_mcp.infocuria import case_list_url, search_url


def test_parse_celex_court_of_justice_judgment():
    parsed = parse_celex("62018CJ0159")
    assert parsed["year"] == "2018"
    assert parsed["descriptor"] == "CJ"
    assert parsed["number"] == "0159"
    assert "Court of Justice" in parsed["document_type"]


def test_is_celex_rejects_non_caselaw():
    assert is_celex("62018CJ0159")
    assert not is_celex("32016R0679")  # a regulation (sector 3), not case-law
    assert not is_celex("C-159/18")


def test_parse_celex_rejects_garbage():
    with pytest.raises(ValueError):
        parse_celex("not-a-celex")


def test_parse_ecli():
    parsed = parse_ecli("ECLI:EU:C:2019:933")
    assert parsed["court_letter"] == "C"
    assert parsed["court"] == "Court of Justice"
    assert parsed["year"] == "2019"
    assert parsed["ordinal"] == "933"


def test_parse_ecli_rejects_non_eu():
    with pytest.raises(ValueError):
        parse_ecli("ECLI:CZ:US:2019:1")


@pytest.mark.parametrize(
    "raw, court, seq, year",
    [
        ("C-159/18", "C", 159, 2018),
        ("C-159/18 P", "C", 159, 2018),  # appeal suffix ignored
        ("T-79/16", "T", 79, 2016),
        ("F-1/05", "F", 1, 2005),
        ("Case C-403/08", "C", 403, 2008),
        ("C-1/99", "C", 1, 1999),  # 2-digit year window: 99 -> 1999
    ],
)
def test_parse_case_number(raw, court, seq, year):
    case = parse_case_number(raw)
    assert case.court_letter == court
    assert case.sequence == seq
    assert case.year == year


def test_case_number_normalised():
    assert parse_case_number("C-159/2018").normalised() == "C-159/18"


def test_parse_case_number_rejects_garbage():
    with pytest.raises(ValueError):
        parse_case_number("hello world")


def test_infocuria_case_list_url_encodes_number():
    url = case_list_url("C-159/18", language="en")
    assert "num=C-159%2F18" in url
    assert "language=en" in url


def test_infocuria_search_url_falls_back_to_en():
    url = search_url("competition law", language="xx")
    assert "text=competition%20law" in url
    assert "language=en" in url
