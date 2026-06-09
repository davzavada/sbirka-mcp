import pytest

from sbirka_mcp.citations import citace_to_stale_url, encode_stale_url


@pytest.mark.parametrize(
    "citace, expected",
    [
        ("89/2012 Sb.", "/sb/2012/89"),
        ("č. 89/2012 Sb.", "/sb/2012/89"),
        ("Zákon č. 89/2012 Sb., občanský zákoník", "/sb/2012/89"),
        ("89/2012 Sb", "/sb/2012/89"),
        ("/sb/2012/89", "/sb/2012/89"),
        ("/sb/2012/89/2024-04-01", "/sb/2012/89"),
        ("/eli/cz/sb/2012/89/2024-04-01", "/sb/2012/89"),
        ("40/2009 Sb.", "/sb/2009/40"),
    ],
)
def test_citace_to_stale_url(citace, expected):
    assert citace_to_stale_url(citace) == expected


def test_encode_stale_url():
    assert encode_stale_url("/sb/2012/89") == "%2Fsb%2F2012%2F89"


@pytest.mark.parametrize("bad", ["", "   ", "není citace", "Sb."])
def test_invalid_citace_raises(bad):
    with pytest.raises(ValueError):
        citace_to_stale_url(bad)
