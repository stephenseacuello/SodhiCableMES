"""Test fixtures for SodhiCable MES — uses a temporary database for isolation."""
import pytest
import os
import sys
import tempfile
import shutil
import sqlite3

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def test_db():
    """Create a temporary test database from schema + seed data."""
    tmp_dir = tempfile.mkdtemp(prefix="sodhicable_test_")
    db_path = os.path.join(tmp_dir, "test_mes.db")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    schema_path = os.path.join(BASE_DIR, "database", "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path) as f:
            conn.executescript(f.read())

    seed_path = os.path.join(BASE_DIR, "database", "seed_data.sql")
    if os.path.exists(seed_path):
        with open(seed_path) as f:
            conn.executescript(f.read())

    views_path = os.path.join(BASE_DIR, "database", "views.sql")
    if os.path.exists(views_path):
        with open(views_path) as f:
            conn.executescript(f.read())

    conn.close()

    yield db_path

    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def client(test_db):
    """Create a test client with isolated database.

    Patches both config.DATABASE and app.DATABASE so that get_db()
    (which uses the module-level import) points at the temp DB.
    """
    import config
    import db as db_module

    original_config_db = config.DATABASE
    original_db_db = db_module.DATABASE

    config.DATABASE = test_db
    db_module.DATABASE = test_db

    from app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE"] = test_db

    with flask_app.test_client() as test_client:
        yield test_client

    config.DATABASE = original_config_db
    db_module.DATABASE = original_db_db
