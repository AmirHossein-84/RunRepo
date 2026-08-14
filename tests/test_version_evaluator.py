"""Unit tests for semantic version parsing and requirement evaluation."""

from runrepo.environment.version import (
    clean_version_string,
    evaluate_version_requirement,
    parse_version_tuple,
)


def test_clean_version_string():
    assert clean_version_string("v22.15.0") == "22.15.0"
    assert clean_version_string("Python 3.14.0") == "3.14.0"
    assert clean_version_string("Docker version 28.3.0, build 332d431") == "28.3.0"
    assert clean_version_string("git version 2.51.0.windows.1") == "2.51.0"
    assert clean_version_string("pnpm 10.12.1") == "10.12.1"
    assert clean_version_string(None) is None
    assert clean_version_string("") is None


def test_parse_version_tuple():
    assert parse_version_tuple("22.15.0") == (22, 15, 0)
    assert parse_version_tuple("3.11") == (3, 11)
    assert parse_version_tuple("v20") == (20,)
    assert parse_version_tuple("2.45.2.windows.1") == (2, 45, 2)
    assert parse_version_tuple("invalid") is None


def test_exact_and_major_version_matching():
    assert evaluate_version_requirement("22.15.0", "22") is True
    assert evaluate_version_requirement("20.10.0", "22") is False
    assert evaluate_version_requirement("3.11.8", "3.11") is True
    assert evaluate_version_requirement("3.12.0", "3.11") is False
    assert evaluate_version_requirement("22.15.0", "22.15.0") is True
    assert evaluate_version_requirement("22.15.1", "22.15.0") is False


def test_relational_operators():
    assert evaluate_version_requirement("22.15.0", ">=22") is True
    assert evaluate_version_requirement("20.10.0", ">=22") is False
    assert evaluate_version_requirement("3.11.4", ">=3.11") is True
    assert evaluate_version_requirement("3.10.0", ">=3.11") is False
    assert evaluate_version_requirement("3.12.0", "<=3.12") is True
    assert evaluate_version_requirement("3.13.0", "<=3.12") is False
    assert evaluate_version_requirement("20.0.0", ">18") is True
    assert evaluate_version_requirement("18.0.0", ">18") is False


def test_compound_ranges():
    assert evaluate_version_requirement("22.10.0", ">=20 <23") is True
    assert evaluate_version_requirement("24.0.0", ">=20 <23") is False
    assert evaluate_version_requirement("18.0.0", ">=20 <23") is False
    assert evaluate_version_requirement("3.12.3", ">=3.11, <3.14") is True
    assert evaluate_version_requirement("3.14.1", ">=3.11, <3.14") is False


def test_semver_caret_and_tilde():
    # Caret: ^22 allows >=22.0.0 <23.0.0
    assert evaluate_version_requirement("22.15.0", "^22.0.0") is True
    assert evaluate_version_requirement("23.0.0", "^22.0.0") is False
    assert evaluate_version_requirement("21.9.0", "^22.0.0") is False

    # Tilde: ~22.3 allows >=22.3.0 <22.4.0
    assert evaluate_version_requirement("22.3.5", "~22.3.0") is True
    assert evaluate_version_requirement("22.4.0", "~22.3.0") is False
    assert evaluate_version_requirement("22.2.0", "~22.3.0") is False


def test_wildcards():
    assert evaluate_version_requirement("18.19.0", "18.x") is True
    assert evaluate_version_requirement("20.0.0", "18.x") is False
    assert evaluate_version_requirement("20.10.0", "20.X") is True
    assert evaluate_version_requirement("22.15.0", "*") is True


def test_or_conditions():
    assert evaluate_version_requirement("18.19.0", "^18.0.0 || ^20.0.0") is True
    assert evaluate_version_requirement("20.10.0", "^18.0.0 || ^20.0.0") is True
    assert evaluate_version_requirement("22.0.0", "^18.0.0 || ^20.0.0") is False


def test_missing_or_empty_versions():
    assert evaluate_version_requirement("22.0.0", "") is True
    assert evaluate_version_requirement("22.0.0", None) is True
    assert evaluate_version_requirement(None, ">=22") is False
    assert evaluate_version_requirement("unparseable", ">=22") is None
