from app.core.config import Settings


def make_settings(owner_ids):
    return Settings(
        bot_token="123456:abcdefghijklmnopqrstuvwxyzABCDE123456",
        database_url="postgresql+asyncpg://u:p@localhost/db",
        redis_url="redis://localhost:6379/0",
        service_owner_ids=owner_ids,
    )


def test_single_owner_id_as_integer():
    assert make_settings(123456789).service_owner_ids == (123456789,)


def test_owner_ids_as_csv_string():
    assert make_settings("123456789,987654321").service_owner_ids == (
        123456789,
        987654321,
    )
