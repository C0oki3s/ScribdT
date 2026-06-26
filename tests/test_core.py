from unittest.mock import MagicMock

import pytest

from scribd_tool.core import read_cookies_from_file, user_id_sequence


class TestReadCookiesFromFile:
    def test_reads_valid_cookies(self, tmp_path):
        f = tmp_path / "cookies.txt"
        f.write_text("session_id=abc123; user_token=xyz789")
        result = read_cookies_from_file(str(f))
        assert result["session_id"] == "abc123"
        assert result["user_token"] == "xyz789"

    def test_missing_file_returns_empty_dict(self, tmp_path, capsys):
        result = read_cookies_from_file(str(tmp_path / "missing.txt"))
        assert result == {}
        assert "not found" in capsys.readouterr().out.lower()

    def test_malformed_cookie_skipped_with_message(self, tmp_path, capsys):
        f = tmp_path / "cookies.txt"
        f.write_text("valid=one; malformed; other=two")
        result = read_cookies_from_file(str(f))
        assert result.get("valid") == "one"
        assert result.get("other") == "two"
        assert "malformed" in capsys.readouterr().out

    def test_cookie_value_with_equals_sign(self, tmp_path):
        f = tmp_path / "cookies.txt"
        f.write_text("token=abc=def=ghi")
        result = read_cookies_from_file(str(f))
        assert result["token"] == "abc=def=ghi"

    def test_strips_surrounding_whitespace(self, tmp_path):
        f = tmp_path / "cookies.txt"
        f.write_text("  session = myvalue  ")
        result = read_cookies_from_file(str(f))
        assert result["session"] == "myvalue"

    def test_multiple_cookies(self, tmp_path):
        f = tmp_path / "cookies.txt"
        f.write_text("a=1; b=2; c=3")
        result = read_cookies_from_file(str(f))
        assert len(result) == 3

    def test_returns_dict(self, tmp_path):
        f = tmp_path / "cookies.txt"
        f.write_text("key=val")
        assert isinstance(read_cookies_from_file(str(f)), dict)


class TestUserIdSequence:
    def test_single_user_id_returns_list_with_that_id(self):
        args = MagicMock()
        args.user_id = 42
        assert list(user_id_sequence(args)) == [42]

    def test_range_returns_inclusive_sequence(self):
        args = MagicMock()
        args.user_id = None
        args.user_start = 1
        args.user_end = 5
        assert list(user_id_sequence(args)) == [1, 2, 3, 4, 5]

    def test_single_id_of_zero_raises(self):
        args = MagicMock()
        args.user_id = 0
        with pytest.raises(ValueError, match="--user-id"):
            user_id_sequence(args)

    def test_user_start_zero_raises(self):
        args = MagicMock()
        args.user_id = None
        args.user_start = 0
        args.user_end = 10
        with pytest.raises(ValueError, match="--user-start"):
            user_id_sequence(args)

    def test_user_end_less_than_start_raises(self):
        args = MagicMock()
        args.user_id = None
        args.user_start = 10
        args.user_end = 5
        with pytest.raises(ValueError, match="--user-end"):
            user_id_sequence(args)

    def test_start_equals_end_returns_single_element(self):
        args = MagicMock()
        args.user_id = None
        args.user_start = 7
        args.user_end = 7
        assert list(user_id_sequence(args)) == [7]

    def test_single_user_id_of_one_is_valid(self):
        args = MagicMock()
        args.user_id = 1
        assert list(user_id_sequence(args)) == [1]

    def test_large_range_correct_length(self):
        args = MagicMock()
        args.user_id = None
        args.user_start = 1
        args.user_end = 100
        result = list(user_id_sequence(args))
        assert len(result) == 100
        assert result[0] == 1
        assert result[-1] == 100
