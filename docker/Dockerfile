FROM python:3.12.4-slim

# --- Пользователь приложения ---
RUN useradd -ms /bin/bash celeryuser

# --- Системные пакеты (+ Xvfb/x11vnc/Openbox и зависимости браузера) ---
# Добавлены iproute2, jq, x11-utils для диагностики и xdpyinfo
RUN apt-get update && apt-get install -y \
    gcc git build-essential g++ \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    curl wget unzip python3-dev netcat-openbsd \
    xvfb x11vnc openbox x11-utils \
    fonts-liberation libasound2 libnss3 libxss1 libxrandr2 libatk1.0-0 libatk-bridge2.0-0 \
    libgbm1 libxshmfence1 libu2f-udev iproute2 jq \
 && rm -rf /var/lib/apt/lists/*

# --- Гарантируем корректную X-сокетную папку (важно: права 1777 создаёт root) ---
RUN mkdir -p /tmp/.X11-unix && \
    chown root:root /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# --- Права на python директории (чтобы celeryuser мог ставить пакеты/обновлять) ---
RUN chown -R celeryuser:celeryuser /usr/local/lib/python3.12 \
 && chown -R celeryuser:celeryuser /usr/local/include/python3.12 \
 && chown -R celeryuser:celeryuser /usr/local/bin

# --- Переменные окружения ---
ENV HOME=/home/celeryuser
ENV PROJECT_ROOT=$HOME/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONBREAKPOINT=ipdb.set_trace
ENV PATH="$HOME/.local/bin:$PATH"
ENV PORT=8000
# Куда Playwright кладёт браузеры (кеш слоя образа/volume)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Xvfb/VNC параметры по умолчанию (можно переопределить в compose)
ENV DISPLAY=:99
ENV VNC_PORT=5900
ENV XVFB_W=1366
ENV XVFB_H=768
ENV XVFB_D=24

# --- Установка Poetry под приложным пользователем ---
USER celeryuser
WORKDIR $HOME
RUN curl -sSL https://install.python-poetry.org | python3 - && poetry --version

# --- Установка зависимостей проекта ---
WORKDIR $PROJECT_ROOT

# сначала только зависимости
COPY --chown=celeryuser:celeryuser pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-root --only main

# затем весь код
COPY --chown=celeryuser:celeryuser . .

# --- Дальнейшие штуки, требующие root (Playwright, права, статические директории) ---
USER root

# Установка Playwright deps и браузера Chromium
RUN python -m playwright install-deps && \
    python -m playwright install chromium

# (Опционально) если используешь patchright — подтянуть артефакты, иначе тихо пропустить
RUN bash -lc 'command -v patchright >/dev/null 2>&1 && patchright install || true'

# Каталог под браузеры
RUN mkdir -p /ms-playwright && \
    chown -R celeryuser:celeryuser /ms-playwright && \
    chmod -R 0755 /ms-playwright

# ✅ Гарантируем наличие статики и vehicle_icons + права для celeryuser
RUN mkdir -p $PROJECT_ROOT/app/static/vehicle_icons && \
    chown -R celeryuser:celeryuser $PROJECT_ROOT

# --- entrypoint: Xvfb + VNC + запуск приложения ---
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# --- Возвращаемся под приложного пользователя ---
USER celeryuser
WORKDIR $PROJECT_ROOT

# --- Порты: API + VNC + CDP ---
EXPOSE 8000 5900 9222

# --- Запуск ---
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
