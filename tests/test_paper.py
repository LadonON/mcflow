import urllib.error

import pytest

from mcflow import paper


def test_fill_response_keeps_stable_releases_from_1_17(fill_response):
    ids = [v.id for v in paper.from_fill_response(fill_response)]
    assert ids == ["26.3", "26.1.1", "1.21.11", "1.20.4", "1.17"]


def test_fill_response_reads_java_and_support(fill_response):
    by_id = {v.id: v for v in paper.from_fill_response(fill_response)}
    assert by_id["26.3"].java_minimum == 25 and by_id["26.3"].supported
    assert by_id["1.21.11"].java_minimum == 21 and not by_id["1.21.11"].supported
    assert by_id["1.20.4"].java_minimum == 17
    assert by_id["1.17"].java_minimum == 16


@pytest.fixture
def versions(fill_response):
    return paper.from_fill_response(fill_response)


def test_resolve_latest(versions):
    assert paper.resolve("latest", versions).id == "26.3"
    assert paper.resolve(" Latest ", versions).id == "26.3"


def test_resolve_exact(versions):
    assert paper.resolve("1.21.11", versions).java_minimum == 21


@pytest.mark.parametrize("too_old", ["1.16.5", "1.8.8", "1.12"])
def test_resolve_rejects_versions_before_1_17(versions, too_old):
    with pytest.raises(paper.UnsupportedPaperVersion, match=r"1\.17 and newer"):
        paper.resolve(too_old, versions)


def test_resolve_rejects_unknown_release(versions):
    with pytest.raises(paper.UnsupportedPaperVersion, match=r"no release called 1\.21\.99"):
        paper.resolve("1.21.99", versions)


@pytest.mark.parametrize("junk", ["26.3-rc-3", "banana", ""])
def test_resolve_rejects_non_release_text(versions, junk):
    with pytest.raises(paper.UnsupportedPaperVersion, match="isn't a Paper release version"):
        paper.resolve(junk, versions)


@pytest.mark.parametrize(("minimum", "lts"), [(16, 17), (17, 17), (21, 21), (25, 25)])
def test_recommended_java_is_lowest_lts_that_fits(minimum, lts):
    assert paper.recommended_java(minimum) == lts


def test_bundled_cache_is_usable():
    cached = paper.load_cached()
    assert cached, "data/paper_versions.json is empty"
    assert all(v.key >= (1, 17) for v in cached)
    assert cached == sorted(cached, key=lambda v: v.key, reverse=True)


def test_falls_back_to_cache_when_offline(monkeypatch):
    def unreachable(timeout=5.0):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(paper, "fetch_live", unreachable)
    versions, source = paper.available_versions(online=True)
    assert source == "cached"
    assert versions == paper.load_cached()
