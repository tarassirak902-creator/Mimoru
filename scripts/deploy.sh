#!/usr/bin/env bash
set -euo pipefail

cd /root/Mimoru/bot

echo "==> Проверка Git..."
git fetch origin
git pull --ff-only origin main

echo "==> Пересборка бота..."
docker compose build bot

echo "==> Перезапуск бота..."
docker compose up -d bot

echo "==> Ожидание запуска..."
sleep 8

echo "==> Статус..."
docker compose ps

echo "==> Последние логи бота..."
docker compose logs --tail=60 bot
