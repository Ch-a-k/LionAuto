#!/bin/bash

echo "🚨 Удаление ВСЕХ контейнеров..."
docker rm -f $(docker ps -aq) 2>/dev/null

echo "🧼 Удаление ВСЕХ образов..."
docker rmi -f $(docker images -q) 2>/dev/null

echo "🧹 Удаление ВСЕХ томов..."
docker volume rm $(docker volume ls -q) 2>/dev/null

echo "✅ Полная очистка завершена!"