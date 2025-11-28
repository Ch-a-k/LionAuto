FROM python:3.12.4-slim

# --- Пользователь приложения ---
RUN useradd -ms /bin/bash celeryuser

# --- Системные пакеты (без Xvfb/x11/playwright-зависимостей) ---
RUN apt-get update && apt-get install -y \
    gcc git build-essential g++ \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    curl wget unzip python3-dev netcat-openbsd \
    iproute2 jq \
 && rm -rf /var/lib/apt/lists/*

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

# Гарантируем наличие статики и vehicle_icons
RUN mkdir -p $PROJECT_ROOT/app/static/vehicle_icons

# --- Порт API ---
EXPOSE 8000

# --- Запуск приложения ---
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
