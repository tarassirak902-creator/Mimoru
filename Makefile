.PHONY: up down logs test lint migrate backup
up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f bot

test:
	pytest -q
	python -m compileall -q app alembic tests

lint:
	ruff check app tests

migrate:
	docker compose run --rm bot alembic upgrade head

backup:
	docker compose exec backup /scripts_backup.sh
