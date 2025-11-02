#!/usr/bin/env bash
set -euo pipefail

# --- дефолтные значения, если не прокинули через env ---
: "${DISPLAY:=:99}"
: "${VNC_PORT:=5900}"
: "${XVFB_W:=1366}"
: "${XVFB_H:=768}"
: "${XVFB_D:=24}"

# --- гарантия существования сокетной папки X (нормальная версия с правами уже создана в Dockerfile) ---
if [ ! -d /tmp/.X11-unix ]; then
  mkdir -p /tmp/.X11-unix || true
  # если мы не root — chmod может не сработать, это ок (в Dockerfile уже правильно создано)
  chmod 1777 /tmp/.X11-unix >/dev/null 2>&1 || true
fi

# --- пароль для VNC (опционально) ---
if [ -n "${VNC_PASS:-}" ]; then
  mkdir -p /home/celeryuser/.vnc
  x11vnc -storepasswd "$VNC_PASS" /home/celeryuser/.vnc/pass 1>/dev/null 2>&1 || true
  VNC_AUTH=(-rfbauth /home/celeryuser/.vnc/pass)
else
  VNC_AUTH=(-nopw)
fi

echo "Starting Xvfb on $DISPLAY (${XVFB_W}x${XVFB_H}x${XVFB_D})"
Xvfb "$DISPLAY" -screen 0 "${XVFB_W}x${XVFB_H}x${XVFB_D}" -ac +extension RANDR +render -noreset &
sleep 0.8

# --- простой оконный менеджер, чтобы окна корректно себя вели ---
openbox >/tmp/openbox.log 2>&1 &

# --- VNC-сервер (локальный; наружу у тебя уже проброшен 127.0.0.1:5900 в compose) ---
echo "Starting x11vnc on port ${VNC_PORT}"
x11vnc -display "$DISPLAY" -forever -shared -rfbport "${VNC_PORT}" -localhost -bg "${VNC_AUTH[@]}" -o /tmp/x11vnc.log || true

# --- вывод краткой диагностики (не критично) ---
echo "PORT=${VNC_PORT}"
command -v ss >/dev/null 2>&1 && ss -lntp | grep -E ':5900|:9222' || true
[ -f /tmp/x11vnc.log ] && tail -n +1 /tmp/x11vnc.log | sed -n '1,5p' || true

# --- запуск основного процесса контейнера (uvicorn/celery и т.п.) ---
exec "$@"
