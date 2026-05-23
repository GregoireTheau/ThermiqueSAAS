import gzip
import sqlite3

import pytest

from thermal_saas.backup import BackupError, create_sqlite_backup_archive


def test_create_sqlite_backup_archive_contains_consistent_database(tmp_path):
    db_path = tmp_path / "thermal_saas.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table beta_data (id integer primary key, value text)")
        connection.execute("insert into beta_data (value) values (?)", ("persisted",))

    archive, created_at = create_sqlite_backup_archive(db_path)
    restored_path = tmp_path / "restored.sqlite"
    restored_path.write_bytes(gzip.decompress(archive))

    with sqlite3.connect(restored_path) as connection:
        value = connection.execute("select value from beta_data").fetchone()[0]

    assert created_at.endswith("Z")
    assert value == "persisted"


def test_create_sqlite_backup_archive_requires_existing_database(tmp_path):
    with pytest.raises(BackupError, match="Database file does not exist"):
        create_sqlite_backup_archive(tmp_path / "missing.sqlite")
