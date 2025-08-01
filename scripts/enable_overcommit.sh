#!/bin/bash

echo "🔧 Включение vm.overcommit_memory=1..."

# Временное включение
sudo sysctl -w vm.overcommit_memory=1

# Проверка и добавление в sysctl.conf
CONF_LINE="vm.overcommit_memory = 1"
CONF_FILE="/etc/sysctl.conf"

if grep -q "^$CONF_LINE" "$CONF_FILE"; then
  echo "✅ Строка уже есть в $CONF_FILE"
else
  echo "$CONF_LINE" | sudo tee -a "$CONF_FILE"
  echo "✅ Строка добавлена в $CONF_FILE"
fi

# Применение
sudo sysctl -p

echo "🎉 Готово! vm.overcommit_memory включено и сохранено."