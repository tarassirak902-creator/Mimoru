#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/Mimoru"
cd "$PROJECT_DIR"

echo "==> Проверка окружения..."
if [[ ! -f .env ]]; then
  echo "ОШИБКА: $PROJECT_DIR/.env не найден. Деплой остановлен."
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "ОШИБКА: на сервере есть локальные изменения в отслеживаемых файлах."
  echo "Сначала сохраните или отмените их, затем повторите деплой:"
  git status --short
  exit 1
fi

echo "==> Получение изменений из GitHub..."
git fetch origin main
git pull --ff-only origin main

echo "==> Проверка docker-compose.yml..."
docker compose config -q

echo "==> Запуск PostgreSQL и Redis..."
docker compose up -d postgres redis

echo "==> Сборка новой версии бота..."
docker compose build bot

echo "==> Перезапуск бота и backup-сервиса..."
docker compose up -d bot backup

echo "==> Ожидание готовности бота..."
BOT_ID="$(docker compose ps -q bot)"
if [[ -z "$BOT_ID" ]]; then
  echo "ОШИБКА: контейнер bot не создан."
  docker compose ps
  exit 1
fi

READY=0
for _ in {1..18}; do
  STATUS="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$BOT_ID" 2>/dev/null || true)"
  case "$STATUS" in
    healthy)
      READY=1
      break
      ;;
    unhealthy|exited|dead)
      echo "ОШИБКА: bot имеет статус: $STATUS"
      docker compose logs --tail=120 bot
      exit 1
      ;;
  esac
  sleep 5
done

if [[ "$READY" -ne 1 ]]; then
  echo "ОШИБКА: bot не стал healthy за 90 секунд."
  docker compose ps
  docker compose logs --tail=120 bot
  exit 1
fi

echo "==> Деплой завершён успешно."
docker compose ps
echo "==> Последние логи бота:"
docker compose logs --tail=60 bot
