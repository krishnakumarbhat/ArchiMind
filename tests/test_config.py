"""Configuration tests for environment normalization and fallback."""

import config


def test_get_database_url_falls_back_for_non_url_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "4b2b89f62c9d1337bcf219fb6a26650b")

    assert config.get_database_url() == config.SQLITE_URL


def test_get_database_url_keeps_valid_postgresql_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.com:5432/postgres")

    assert config.get_database_url() == "postgresql+psycopg://user:secret@example.com:5432/postgres"