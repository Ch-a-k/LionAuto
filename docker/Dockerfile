FROM python:3.12.4-slim

# Создаем пользователя
RUN useradd -ms /bin/bash celeryuser

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc git build-essential g++ \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    curl wget unzip python3-dev netcat-openbsd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Переменные окружения
ENV HOME=/home/celeryuser
ENV PROJECT_ROOT=$HOME/app
ENV PYTHONDONTWRITEBYTECODE=1 
ENV PYTHONUNBUFFERED=1
ENV PYTHONBREAKPOINT=ipdb.set_trace
ENV PATH="$HOME/.local/bin:$PATH"
ENV PORT=8000

# Установка Poetry
USER celeryuser
WORKDIR $HOME
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN poetry --version

# Переход в директорию проекта
WORKDIR $PROJECT_ROOT

# Копируем зависимости
COPY --chown=celeryuser:celeryuser pyproject.toml poetry.lock ./

# Устанавливаем зависимости без dev-зависимостей
RUN poetry config virtualenvs.create false && poetry install --no-root --only main

# Копируем весь код проекта
COPY --chown=celeryuser:celeryuser . .

# Открываем порт (для backend сервиса)
EXPOSE 8000

# Команда по умолчанию (будет переопределена в docker-compose)
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]