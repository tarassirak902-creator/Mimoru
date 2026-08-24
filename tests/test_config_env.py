from app.core.config import Settings


def test_owner_ids_as_csv_environment_value(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:" + "abcdefghijklmnopqrstuvwxyzABCDE123456")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SERVICE_OWNER_IDS", "123456789,987654321")

    assert Settings().service_owner_ids == (123456789, 987654321)
