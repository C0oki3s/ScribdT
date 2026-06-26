import queue
import sqlite3
import threading
from unittest.mock import MagicMock

import pytest

from scribd_tool.db import (
    NoDocumentsFoundError,
    create_db,
    insert_user,
    retrieve_data,
    search_by_username,
)


class TestCreateDb:
    def test_creates_file(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        assert (tmp_path / "test.db").exists()

    def test_creates_users_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert c.fetchone() is not None
        conn.close()

    def test_creates_index_on_user_id(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_user_id'")
        assert c.fetchone() is not None
        conn.close()

    def test_idempotent_second_call_does_not_raise(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        create_db(db_path)

    def test_none_filename_is_no_op(self):
        create_db(None)

    def test_users_table_has_expected_columns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in c.fetchall()}
        conn.close()
        assert {"id", "user_id", "username", "img_url"}.issubset(columns)


class TestInsertUser:
    def test_inserts_single_user(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)

        q = queue.Queue()
        t = threading.Thread(target=insert_user, args=(q, db_path))
        t.start()
        q.put((1, "alice", "http://img.example.com/alice.jpg"))
        q.put(None)
        t.join(timeout=5)

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT user_id, username, img_url FROM users WHERE user_id = 1")
        row = c.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 1
        assert row[1] == "alice"
        assert row[2] == "http://img.example.com/alice.jpg"

    def test_inserts_multiple_users(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)

        q = queue.Queue()
        t = threading.Thread(target=insert_user, args=(q, db_path))
        t.start()
        for i in range(5):
            q.put((i + 1, f"user{i}", f"http://img.example.com/{i}.jpg"))
        q.put(None)
        t.join(timeout=5)

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        assert c.fetchone()[0] == 5
        conn.close()

    def test_stops_on_none_sentinel(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)

        q = queue.Queue()
        t = threading.Thread(target=insert_user, args=(q, db_path))
        t.start()
        q.put(None)
        t.join(timeout=5)
        assert not t.is_alive()


class TestRetrieveData:
    def _seed(self, db_path, user_id, username, img_url):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO users (user_id, username, img_url) VALUES (?, ?, ?)",
            (user_id, username, img_url),
        )
        conn.commit()
        conn.close()

    def test_prints_user_data(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        self._seed(db_path, 42, "bob", "http://example.com/bob.jpg")

        args = MagicMock()
        args.db = db_path
        args.users = True
        retrieve_data(args)

        out = capsys.readouterr().out
        assert "bob" in out
        assert "42" in out

    def test_users_flag_false_prints_nothing_from_users(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        self._seed(db_path, 1, "alice", "http://example.com/alice.jpg")

        args = MagicMock()
        args.db = db_path
        args.users = False
        retrieve_data(args)

        out = capsys.readouterr().out
        assert "alice" not in out


class TestSearchByUsername:
    def _seed(self, db_path, user_id, username, img_url="http://example.com/img.jpg"):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO users (user_id, username, img_url) VALUES (?, ?, ?)",
            (user_id, username, img_url),
        )
        conn.commit()
        conn.close()

    def test_finds_exact_match(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        self._seed(db_path, 10, "charlie")

        search_by_username("charlie", db_file=db_path)
        assert "charlie" in capsys.readouterr().out

    def test_finds_partial_match(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        self._seed(db_path, 11, "david_smith")

        search_by_username("david", db_file=db_path)
        assert "david_smith" in capsys.readouterr().out

    def test_no_match_prints_no_results_message(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)

        search_by_username("nonexistent", db_file=db_path)
        assert "No results found" in capsys.readouterr().out

    def test_multiple_matches_all_printed(self, tmp_path, capsys):
        db_path = str(tmp_path / "test.db")
        create_db(db_path)
        self._seed(db_path, 20, "eve_a")
        self._seed(db_path, 21, "eve_b")

        search_by_username("eve", db_file=db_path)
        out = capsys.readouterr().out
        assert "eve_a" in out
        assert "eve_b" in out


class TestNoDocumentsFoundError:
    def test_is_exception_subclass(self):
        assert issubclass(NoDocumentsFoundError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(NoDocumentsFoundError):
            raise NoDocumentsFoundError("test message")
