import json

import pytest

from scribd_tool.utils import (
    PRESIDIO_SUPPORTED_ENTITIES,
    _candidate_extensions,
    _clean_string_list,
    _has_useful_text,
    decode_text,
    extract_html_text,
    load_filter_config,
    normalize_detectors,
    normalize_entities,
    normalize_filter_config,
    normalize_presidio_entities,
)


class TestNormalizeFilterConfig:
    def test_empty_dict_returns_defaults(self):
        config = normalize_filter_config({})
        assert config["entities"] is None
        assert isinstance(config["detectors"], list)
        assert config["exclude_terms"] == []
        assert config["exclude_regex"] == []

    def test_list_input_sets_entities(self):
        config = normalize_filter_config(["EMAIL_ADDRESS", "PERSON"])
        assert "EMAIL_ADDRESS" in config["entities"]
        assert "PERSON" in config["entities"]

    def test_dict_with_entities(self):
        config = normalize_filter_config({"entities": ["EMAIL_ADDRESS"]})
        assert config["entities"] == ["EMAIL_ADDRESS"]

    def test_score_threshold_out_of_range_raises(self):
        with pytest.raises(ValueError):
            normalize_filter_config({"score_threshold": 1.5})

    def test_score_threshold_negative_raises(self):
        with pytest.raises(ValueError):
            normalize_filter_config({"score_threshold": -0.1})

    def test_gliner_threshold_out_of_range_raises(self):
        with pytest.raises(ValueError):
            normalize_filter_config({"gliner_threshold": -0.1})

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            normalize_filter_config("invalid_string")

    def test_entity_alias_resolved(self):
        config = normalize_filter_config({"entities": ["SSN"]})
        assert "US_SSN" in config["entities"]

    def test_address_alias_resolved(self):
        config = normalize_filter_config({"entities": ["ADDRESS"]})
        assert "LOCATION" in config["entities"]

    def test_none_returns_defaults(self):
        config = normalize_filter_config(None)
        assert config["entities"] is None

    def test_presidio_entities_derived_from_entities(self):
        config = normalize_filter_config({"entities": ["EMAIL_ADDRESS", "CUSTOM_ONE"]})
        assert "EMAIL_ADDRESS" in config["presidio_entities"]
        assert "CUSTOM_ONE" not in config["presidio_entities"]

    def test_score_threshold_stored_as_float(self):
        config = normalize_filter_config({"score_threshold": "0.7"})
        assert config["score_threshold"] == 0.7
        assert isinstance(config["score_threshold"], float)

    def test_detectors_passed_through(self):
        config = normalize_filter_config({"detectors": ["regex", "secrets"]})
        assert config["detectors"] == ["regex", "secrets"]


class TestNormalizeEntities:
    def test_none_returns_none(self):
        assert normalize_entities(None) is None

    def test_empty_list_returns_none(self):
        assert normalize_entities([]) is None

    def test_alias_ssn_resolved(self):
        result = normalize_entities(["SSN"])
        assert "US_SSN" in result

    def test_alias_dob_resolved(self):
        result = normalize_entities(["DOB"])
        assert "DATE_TIME" in result

    def test_unknown_entity_uppercased(self):
        result = normalize_entities(["custom_type"])
        assert "CUSTOM_TYPE" in result

    def test_deduplication(self):
        result = normalize_entities(["PERSON", "PERSON"])
        assert result.count("PERSON") == 1

    def test_output_is_sorted(self):
        result = normalize_entities(["PERSON", "EMAIL_ADDRESS"])
        assert result == sorted(result)

    def test_whitespace_stripped(self):
        result = normalize_entities(["  PERSON  "])
        assert "PERSON" in result

    def test_blank_entries_skipped(self):
        result = normalize_entities(["PERSON", "", "  "])
        assert "" not in result
        assert "PERSON" in result


class TestNormalizePresidioEntities:
    def test_none_returns_none(self):
        assert normalize_presidio_entities(None) is None

    def test_filters_out_custom_entities(self):
        result = normalize_presidio_entities(["EMAIL_ADDRESS", "MY_CUSTOM_ENTITY"])
        assert "MY_CUSTOM_ENTITY" not in result
        assert "EMAIL_ADDRESS" in result

    def test_all_non_presidio_returns_none(self):
        result = normalize_presidio_entities(["CUSTOM_ENTITY_ONE", "CUSTOM_ENTITY_TWO"])
        assert result is None

    def test_known_presidio_entities_pass_through(self):
        known = list(PRESIDIO_SUPPORTED_ENTITIES)[:3]
        result = normalize_presidio_entities(known)
        for entity in known:
            assert entity in result

    def test_output_is_sorted(self):
        entities = ["URL", "EMAIL_ADDRESS", "PERSON"]
        result = normalize_presidio_entities(entities)
        assert result == sorted(result)


class TestNormalizeDetectors:
    def test_string_split_on_comma(self):
        result = normalize_detectors("regex,presidio", [])
        assert "regex" in result
        assert "presidio" in result

    def test_list_input_returned(self):
        result = normalize_detectors(["regex"], [])
        assert result == ["regex"]

    def test_none_returns_default(self):
        default = ["regex", "presidio"]
        assert normalize_detectors(None, default) == default

    def test_empty_list_returns_default(self):
        default = ["regex"]
        assert normalize_detectors([], default) == default

    def test_strips_whitespace(self):
        result = normalize_detectors(" regex , secrets ", [])
        assert result == ["regex", "secrets"]


class TestCleanStringList:
    def test_none_returns_none(self):
        assert _clean_string_list(None) is None

    def test_string_wrapped_in_list(self):
        assert _clean_string_list("hello") == ["hello"]

    def test_list_items_stripped(self):
        assert _clean_string_list(["  a  ", "b"]) == ["a", "b"]

    def test_empty_strings_removed(self):
        assert _clean_string_list(["a", "", "  "]) == ["a"]

    def test_empty_list_returns_empty(self):
        assert _clean_string_list([]) == []


class TestCandidateExtensions:
    def test_auto_returns_all_three(self):
        assert _candidate_extensions("auto") == ["txt", "pdf", "docx"]

    def test_none_returns_all_three(self):
        assert _candidate_extensions(None) == ["txt", "pdf", "docx"]

    def test_specific_pdf(self):
        assert _candidate_extensions("pdf") == ["pdf"]

    def test_specific_txt(self):
        assert _candidate_extensions("txt") == ["txt"]

    def test_specific_docx(self):
        assert _candidate_extensions("docx") == ["docx"]


class TestHasUsefulText:
    def test_empty_string_is_not_useful(self):
        assert _has_useful_text("") is False

    def test_none_is_not_useful(self):
        assert _has_useful_text(None) is False

    def test_short_text_is_not_useful(self):
        assert _has_useful_text("hello") is False

    def test_exactly_20_chars_is_useful(self):
        assert _has_useful_text("a" * 20) is True

    def test_whitespace_only_is_not_useful(self):
        assert _has_useful_text("   " * 20) is False

    def test_19_chars_is_not_useful(self):
        assert _has_useful_text("a" * 19) is False


class TestExtractHtmlText:
    def test_strips_script_tags(self):
        html = b"<html><body><script>alert(1)</script><p>Hello</p></body></html>"
        text = extract_html_text(html)
        assert "alert" not in text
        assert "Hello" in text

    def test_strips_style_tags(self):
        html = b"<html><head><style>.red{color:red}</style></head><body>Text</body></html>"
        text = extract_html_text(html)
        assert "color" not in text
        assert "Text" in text

    def test_strips_noscript_tags(self):
        html = b"<body><noscript>Enable JS</noscript><p>Real content</p></body>"
        text = extract_html_text(html)
        assert "Enable JS" not in text
        assert "Real content" in text

    def test_extracts_paragraph_text(self):
        html = b"<p>Hello World</p>"
        text = extract_html_text(html)
        assert "Hello World" in text


class TestDecodeText:
    def test_utf8_decoded(self):
        content = "Hello World".encode("utf-8")
        assert decode_text(content) == "Hello World"

    def test_explicit_encoding_used(self):
        content = "Héllo".encode("utf-8")
        assert decode_text(content, "utf-8") == "Héllo"

    def test_latin1_fallback(self):
        content = b"\xe9\xe0\xfc"
        result = decode_text(content)
        assert isinstance(result, str)

    def test_returns_string(self):
        content = b"plain bytes"
        result = decode_text(content)
        assert isinstance(result, str)


class TestLoadFilterConfig:
    def test_loads_valid_json(self, tmp_path):
        data = {"entities": ["EMAIL_ADDRESS"], "score_threshold": 0.5}
        f = tmp_path / "filters.json"
        f.write_text(json.dumps(data))
        config = load_filter_config(str(f))
        assert "EMAIL_ADDRESS" in config["entities"]

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_filter_config("/nonexistent/path/filters.json")

    def test_loads_list_format(self, tmp_path):
        data = ["EMAIL_ADDRESS", "PERSON"]
        f = tmp_path / "filters.json"
        f.write_text(json.dumps(data))
        config = load_filter_config(str(f))
        assert "EMAIL_ADDRESS" in config["entities"]
        assert "PERSON" in config["entities"]
