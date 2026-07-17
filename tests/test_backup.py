from __future__ import annotations

import sqlite3

import pytest

from openpool import backup, db


def test_native_backup_preserves_integrity_and_rows_while_source_is_open(tmp_path):
    source = tmp_path / "openpool.sqlite"
    source_conn = db.connect(source)
    try:
        db.init_db(source_conn)
        db.create_pool(
            source_conn,
            {"id": "pool", "name": "Backup Test", "volume_gallons": 10_000},
        )
        db.create_reading(source_conn, "pool", {"fc": 4, "cya": 40})
        destination = tmp_path / "backups" / "openpool-copy.sqlite"
        backup.backup_sqlite(source, destination)
    finally:
        source_conn.close()

    restored = sqlite3.connect(destination)
    try:
        assert restored.execute("pragma integrity_check").fetchone()[0] == "ok"
        assert restored.execute("select count(*) from pool_profiles").fetchone()[0] == 1
        assert restored.execute("select count(*) from test_readings").fetchone()[0] == 1
    finally:
        restored.close()


def test_native_backup_refuses_overwrite(tmp_path):
    source = tmp_path / "openpool.sqlite"
    sqlite3.connect(source).close()
    destination = tmp_path / "existing.sqlite"
    destination.write_bytes(b"keep me")

    with pytest.raises(FileExistsError, match="already exists"):
        backup.backup_sqlite(source, destination)

    assert destination.read_bytes() == b"keep me"


def test_native_backup_does_not_overwrite_file_created_during_publish(
    tmp_path, monkeypatch
):
    source = tmp_path / "openpool.sqlite"
    sqlite3.connect(source).close()
    destination = tmp_path / "raced.sqlite"
    real_link = backup.os.link

    def create_competing_file_then_link(temporary, target):
        destination.write_bytes(b"competitor")
        return real_link(temporary, target)

    monkeypatch.setattr(backup.os, "link", create_competing_file_then_link)

    with pytest.raises(FileExistsError):
        backup.backup_sqlite(source, destination)

    assert destination.read_bytes() == b"competitor"
    assert not list(tmp_path.glob(".raced.sqlite.*.tmp"))


def test_native_backup_refuses_live_database_as_destination(tmp_path):
    source = tmp_path / "openpool.sqlite"
    sqlite3.connect(source).close()

    with pytest.raises(ValueError, match="must differ"):
        backup.backup_sqlite(source, source)


def test_backup_cli_writes_requested_output(tmp_path, capsys):
    source = tmp_path / "openpool.sqlite"
    conn = sqlite3.connect(source)
    conn.execute("create table sample (value text)")
    conn.execute("insert into sample values ('kept')")
    conn.commit()
    conn.close()
    output = tmp_path / "backup.sqlite"

    assert backup.main(["--source", str(source), "--output", str(output)]) == 0

    assert output.is_file()
    assert "Backup complete:" in capsys.readouterr().out
