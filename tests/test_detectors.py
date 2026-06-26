import pytest

from scribd_tool.detectors import (
    DEFAULT_DETECTORS,
    DetectionResult,
    filter_by_entities,
    merge_results,
    normalize_detector_names,
    passes_luhn,
    reject_excluded_results,
    run_regex_validators,
    run_secret_scanner,
    text_chunks,
)


class TestPassesLuhn:
    def test_valid_visa(self):
        assert passes_luhn("4532015112830366") is True

    def test_valid_mastercard(self):
        assert passes_luhn("5425233430109903") is True

    def test_invalid_card(self):
        assert passes_luhn("1234567890123456") is False

    def test_too_short(self):
        assert passes_luhn("123456789012") is False

    def test_with_spaces(self):
        assert passes_luhn("4532 0151 1283 0366") is True

    def test_with_dashes(self):
        assert passes_luhn("4532-0151-1283-0366") is True


class TestRunRegexValidators:
    def test_detects_email(self):
        results = run_regex_validators("Contact us at user@example.com for info.")
        emails = [r for r in results if r.entity_type == "EMAIL_ADDRESS"]
        assert len(emails) == 1
        assert emails[0].score == 0.92

    def test_detects_ip_address(self):
        results = run_regex_validators("Server at 192.168.1.1 is down.")
        ips = [r for r in results if r.entity_type == "IP_ADDRESS"]
        assert len(ips) >= 1

    def test_detects_url(self):
        results = run_regex_validators("Visit https://example.com/page for details.")
        urls = [r for r in results if r.entity_type == "URL"]
        assert len(urls) >= 1

    def test_detects_phone(self):
        results = run_regex_validators("Call +18005551234 now.")
        phones = [r for r in results if r.entity_type == "PHONE_NUMBER"]
        assert len(phones) >= 1

    def test_rejects_invalid_credit_card(self):
        results = run_regex_validators("Card: 1234567890123456")
        cards = [r for r in results if r.entity_type == "CREDIT_CARD"]
        assert len(cards) == 0

    def test_detects_valid_credit_card(self):
        results = run_regex_validators("Card: 4532015112830366")
        cards = [r for r in results if r.entity_type == "CREDIT_CARD"]
        assert len(cards) == 1

    def test_no_results_on_plain_text(self):
        results = run_regex_validators("Hello world, no pii here at all.")
        assert results == []

    def test_result_span_is_within_text(self):
        text = "Email me at admin@corp.io please."
        results = run_regex_validators(text)
        emails = [r for r in results if r.entity_type == "EMAIL_ADDRESS"]
        assert len(emails) == 1
        assert text[emails[0].start:emails[0].end] == "admin@corp.io"


class TestRunSecretScanner:
    def test_detects_password(self):
        results = run_secret_scanner("password=mysecretpassword123")
        passwords = [r for r in results if r.entity_type == "PASSWORD_CANDIDATE"]
        assert len(passwords) >= 1

    def test_detects_api_key(self):
        results = run_secret_scanner("api_key=abcdefghijklmnopqrstuvwxyz123456")
        keys = [r for r in results if r.entity_type == "API_KEY"]
        assert len(keys) >= 1

    def test_detects_aws_access_key(self):
        # Pattern requires exactly AKIA + 16 uppercase/digit chars (20 total)
        results = run_secret_scanner("AKIAIOSFODNN7EXAMPLE")
        aws = [r for r in results if r.entity_type == "AWS_ACCESS_KEY"]
        assert len(aws) >= 1

    def test_detects_private_key_header(self):
        results = run_secret_scanner("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK...")
        pks = [r for r in results if r.entity_type == "PRIVATE_KEY"]
        assert len(pks) >= 1

    def test_detects_jwt(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        results = run_secret_scanner(jwt)
        jwts = [r for r in results if r.entity_type == "JWT"]
        assert len(jwts) >= 1

    def test_no_secrets_in_plain_text(self):
        results = run_secret_scanner("The quick brown fox jumps over the lazy dog.")
        assert results == []

    def test_source_is_secrets(self):
        results = run_secret_scanner("AKIAIOSFODNN7EXAMPLE1234")
        assert all(r.source == "secrets" for r in results)


class TestFilterByEntities:
    def _make(self, entity_type):
        return DetectionResult(0, 10, entity_type, 0.9, "regex")

    def test_none_filter_returns_all(self):
        results = [self._make("EMAIL_ADDRESS"), self._make("PERSON")]
        assert filter_by_entities(results, None) == results

    def test_filters_to_matching_type(self):
        results = [self._make("EMAIL_ADDRESS"), self._make("PERSON")]
        filtered = filter_by_entities(results, ["EMAIL_ADDRESS"])
        assert len(filtered) == 1
        assert filtered[0].entity_type == "EMAIL_ADDRESS"

    def test_case_insensitive_match(self):
        results = [self._make("EMAIL_ADDRESS")]
        assert len(filter_by_entities(results, ["email_address"])) == 1

    def test_empty_entity_list_returns_all(self):
        results = [self._make("EMAIL_ADDRESS")]
        assert filter_by_entities(results, []) == results

    def test_no_match_returns_empty(self):
        results = [self._make("EMAIL_ADDRESS")]
        assert filter_by_entities(results, ["PERSON"]) == []


class TestRejectExcludedResults:
    def _make(self, start, end):
        return DetectionResult(start, end, "EMAIL_ADDRESS", 0.9, "regex")

    def test_excludes_exact_term(self):
        text = "admin@example.com"
        results = [self._make(0, len(text))]
        config = {"exclude_terms": ["admin@example.com"], "exclude_regex": []}
        assert reject_excluded_results(results, text, config) == []

    def test_excludes_by_regex(self):
        text = "noreply@example.com"
        results = [self._make(0, len(text))]
        config = {"exclude_terms": [], "exclude_regex": ["noreply"]}
        assert reject_excluded_results(results, text, config) == []

    def test_keeps_non_excluded(self):
        text = "user@example.com"
        results = [self._make(0, len(text))]
        config = {"exclude_terms": ["admin@example.com"], "exclude_regex": []}
        assert len(reject_excluded_results(results, text, config)) == 1

    def test_exclude_term_case_insensitive(self):
        text = "Admin@Example.com"
        results = [self._make(0, len(text))]
        config = {"exclude_terms": ["admin@example.com"], "exclude_regex": []}
        assert reject_excluded_results(results, text, config) == []

    def test_empty_config_keeps_all(self):
        text = "user@example.com"
        results = [self._make(0, len(text))]
        config = {"exclude_terms": [], "exclude_regex": []}
        assert len(reject_excluded_results(results, text, config)) == 1


class TestMergeResults:
    def test_non_overlapping_preserved(self):
        results = [
            DetectionResult(0, 5, "EMAIL_ADDRESS", 0.9, "regex"),
            DetectionResult(10, 15, "PERSON", 0.8, "presidio"),
        ]
        merged = merge_results(results)
        assert len(merged) == 2

    def test_higher_score_wins_on_overlap(self):
        results = [
            DetectionResult(0, 10, "EMAIL_ADDRESS", 0.7, "regex"),
            DetectionResult(0, 10, "PERSON", 0.9, "presidio"),
        ]
        merged = merge_results(results)
        assert len(merged) == 1
        assert merged[0].score == 0.9

    def test_same_type_overlap_merges_sources(self):
        results = [
            DetectionResult(0, 10, "EMAIL_ADDRESS", 0.7, "regex"),
            DetectionResult(0, 10, "EMAIL_ADDRESS", 0.9, "presidio"),
        ]
        merged = merge_results(results)
        assert len(merged) == 1
        sources = merged[0].metadata.get("merged_sources", [])
        assert "regex" in sources
        assert "presidio" in sources

    def test_output_sorted_by_start(self):
        results = [
            DetectionResult(10, 20, "PERSON", 0.8, "presidio"),
            DetectionResult(0, 5, "EMAIL_ADDRESS", 0.9, "regex"),
        ]
        merged = merge_results(results)
        assert merged[0].start == 0
        assert merged[1].start == 10

    def test_empty_input(self):
        assert merge_results([]) == []

    def test_single_result_unchanged(self):
        r = DetectionResult(0, 5, "PERSON", 0.8, "regex")
        merged = merge_results([r])
        assert len(merged) == 1
        assert merged[0].entity_type == "PERSON"


class TestTextChunks:
    def test_short_text_single_chunk(self):
        text = "Hello world"
        chunks = list(text_chunks(text))
        assert chunks == [(0, text)]

    def test_long_text_yields_multiple_chunks(self):
        text = "word " * 600
        chunks = list(text_chunks(text))
        assert len(chunks) > 1

    def test_first_chunk_starts_at_zero(self):
        text = "a " * 2000
        chunks = list(text_chunks(text))
        assert chunks[0][0] == 0

    def test_last_chunk_reaches_end_of_text(self):
        text = "a " * 2000
        chunks = list(text_chunks(text))
        last_offset, last_chunk = chunks[-1]
        assert last_offset + len(last_chunk) == len(text)

    def test_no_empty_chunks(self):
        text = "word " * 600
        for _, chunk in text_chunks(text):
            assert len(chunk) > 0

    def test_exact_chunk_size_boundary(self):
        text = "a" * 2500
        chunks = list(text_chunks(text))
        assert len(chunks) == 1

    def test_just_over_chunk_size(self):
        text = "a" * 2501
        chunks = list(text_chunks(text))
        assert len(chunks) > 1


class TestNormalizeDetectorNames:
    def test_comma_string_parsed(self):
        assert normalize_detector_names("regex,presidio") == ["regex", "presidio"]

    def test_list_input_preserved(self):
        assert normalize_detector_names(["regex", "gliner"]) == ["regex", "gliner"]

    def test_none_returns_defaults(self):
        assert normalize_detector_names(None) == DEFAULT_DETECTORS

    def test_empty_list_returns_defaults(self):
        assert normalize_detector_names([]) == DEFAULT_DETECTORS

    def test_whitespace_stripped(self):
        assert normalize_detector_names(" regex , presidio ") == ["regex", "presidio"]

    def test_lowercased(self):
        assert normalize_detector_names("REGEX,GLINER") == ["regex", "gliner"]
