from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def reference_examples() -> dict:
    return json.loads((FIXTURES / "public_reference_examples.json").read_text())


@pytest.fixture
def conn(tmp_path):
    from openpool import db

    connection = db.connect(tmp_path / "openpool.sqlite")
    db.init_db(connection)
    db.ensure_default_pool(connection, "example", "America/Phoenix")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("OPENPOOL_DB", str(tmp_path / "openpool.sqlite"))
    monkeypatch.setenv("OPENPOOL_DEFAULT_POOL_ID", "example")
    monkeypatch.setenv("OPENPOOL_TIMEZONE", "America/Phoenix")

    from openpool.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
