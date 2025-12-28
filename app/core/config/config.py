from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from hashlib import sha256
from pathlib import Path

class Settings(BaseSettings):
    """Конфигурация приложения из .env и другие настройки"""
    
    # Основные настройки
    app_name: str = "LA-Auctions API"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 3
    debug: bool = True

    # PostgreSQL
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    database_url: str

    # Redis
    redis_host: str
    redis_port: int
    redis_url: str

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    # App Security
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # CORS settings
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://fadder.vercel.app",
        "http://fadder.vercel.app"

    ]
    

    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str = "la-docs"
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None  # Для MinIO или S3-совместимых хранилищ
    
    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC_AUDIT_LOGS: str
    KAFKA_TOPIC_NOTIFICATIONS: str
    KAFKA_GROUP_ID: str
    KAFKA_AUTO_OFFSET_RESET: str
    KAFKA_ENABLE_AUTO_COMMIT: bool

    # Clamva Settings
    CLAMAV_HOST: str
    CLAMAV_PORT: int

    # Encryption
    AUCTION_ENCRYPTION_KEY: str

    #Contabo s3 storage
    S3_CONTABO_ENDPOINT: str
    S3_CONTABO_ACCESS_KEY: str
    S3_CONTABO_SECRET_KEY: str
    S3_CONTABO_BUCKET: str
    S3_CONTABO_REGION: str
    S3_CONTABO_ADDRESSING_STYLE: str
    CONTABO_S3_PUBLIC_URL: str

    #Default User
    PASSWORD: str
    EMAIL: str

    #Copart simple user
    COPART_USER: str
    COPART_PASS: str
    HEADLESS: bool = True
    COPART_AUTOSTART: bool = True

    first_superuser_email: str
    first_superuser_password: str

    CACHE_KEY: str = "lot_refine_automobile"
    CACHE_TTL: int = 1800
    
    media_root: Path = Path("/var/www/media")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def ENCRYPTION_KEY(self) -> bytes:
        # Преобразуем hex-строку в байты
        return bytes.fromhex(self.AUCTION_ENCRYPTION_KEY)

    @staticmethod
    def get_user_secret_key(user_id: int, user_salt: str = "") -> str:
        """
        Генерирует уникальный секретный ключ для пользователя
        """
        base_str = f"{Settings.secret_key}-{user_id}-{user_salt}"
        return sha256(base_str.encode()).hexdigest()

settings = Settings()