"""
Tests for business_rules/validators.py's own additions - specifically
looks_like_rijksregisternummer, which has no prior art in this codebase
(the live conversation flow enforces "never ask for one" by simply never
asking; this is a new detector for manual lead creation, a human typing
into a form). The other validators (validate_ean/email/phone/date_of_birth,
is_adult, is_region_covered) are already covered end-to-end via
tests/test_rules.py, which calls them through conversation_engine.rules's
re-export - this file only adds what's new here.
"""

from business_rules.validators import looks_like_rijksregisternummer


def test_valid_rrn_checksum_is_detected():
    # 85.07.30-033.28: a well-known publicly-documented example RRN with a
    # correct mod-97 check digit (born-before-2000 branch).
    assert looks_like_rijksregisternummer("85073003328") is True


def test_valid_rrn_with_separators_is_detected():
    assert looks_like_rijksregisternummer("85.07.30-033.28") is True


def test_random_11_digit_string_with_bad_checksum_is_not_flagged():
    assert looks_like_rijksregisternummer("12345678901") is False


def test_wrong_length_is_never_flagged():
    assert looks_like_rijksregisternummer("123456789") is False
    assert looks_like_rijksregisternummer("1234567890123") is False


def test_non_numeric_value_is_never_flagged():
    assert looks_like_rijksregisternummer("marie.lambert@example.com") is False


def test_none_and_empty_are_never_flagged():
    assert looks_like_rijksregisternummer(None) is False
    assert looks_like_rijksregisternummer("") is False
