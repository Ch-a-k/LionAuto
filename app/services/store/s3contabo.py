# app/services/store/s3.py
from __future__ import annotations

import os
from typing import Tuple, Optional, Any

import anyio
import boto3
from botocore.client import Config
from loguru import logger
from app.core.config import settings


class S3Service:
    """
    Универсальный S3-сервис под Contabo (совместим и с AWS S3/MinIO).
    Позволяет загружать любые бинарные файлы (фото/видео/PDF/др. документы).

    Ожидаемые переменные окружения / settings:
      - S3_CONTABO_ENDPOINT=https://usc1.contabostorage.com
      - S3_CONTABO_ACCESS_KEY=...
      - S3_CONTABO_SECRET_KEY=...
      - S3_CONTABO_BUCKET=fadder
      - S3_CONTABO_REGION=usc1 (опционально)
      - S3_CONTABO_ADDRESSING_STYLE=path
      - CONTABO_S3_PUBLIC_BASE_URL=https://usc1.contabostorage.com/<storageName>:fadder
        (опционально, чтобы строить публичные ссылки как в панели Contabo)
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region_name: Optional[str] = None,
        addressing_style: str = "path",
        signature_version: str = "s3v4",
        public_base_url: Optional[str] = None,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket = bucket

        # если передали кастомный public_base_url (как у Contabo c "storageName:bucket") — используем его
        if public_base_url:
            self.public_base_url = public_base_url.rstrip("/")
        else:
            # дефолтный вариант: endpoint/bucket
            self.public_base_url = f"{self.endpoint_url}/{self.bucket}"

        cfg = Config(
            signature_version=signature_version,
            s3={"addressing_style": addressing_style},
        )

        session = boto3.session.Session()
        self.client = session.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=self.endpoint_url,
            region_name=region_name,
            config=cfg,
        )

    async def upload_fileobj(
        self,
        fileobj: Any,
        key: str,
        content_type: str = "application/octet-stream",
        public_read: bool = False,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Загрузка потока (любой тип: фото/видео/PDF/и т.д.) по ключу key.
        Возвращает s3://bucket/key
        """
        extra_args = {"ContentType": content_type}
        if public_read:
            extra_args["ACL"] = "public-read"
        if metadata:
            extra_args["Metadata"] = metadata

        def _do_upload() -> None:
            fileobj.seek(0)
            self.client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=self.bucket,
                Key=key,
                ExtraArgs=extra_args,
            )

        try:
            await anyio.to_thread.run_sync(_do_upload)
            s3_path = f"s3://{self.bucket}/{key}"
            logger.info(f"Uploaded to {s3_path}")
            return s3_path
        except Exception:
            logger.exception(f"Failed to upload {key} to bucket {self.bucket}")
            raise

    def get_object_stream(self, key: str) -> Tuple[Any, str, Optional[int]]:
        """
        Возвращает поток (body), content-type и content-length для скачивания.
        """
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
            body = resp["Body"]
            ct = resp.get("ContentType", "application/octet-stream")
            cl = resp.get("ContentLength")
            return body, ct, cl
        except Exception:
            logger.exception(f"Failed to get object stream for key={key}")
            raise

    def delete_object(self, key: str) -> None:
        """
        Удаление объекта по ключу.
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted s3://{self.bucket}/{key}")
        except Exception:
            logger.exception(f"Failed to delete s3://{self.bucket}/{key}")
            raise

    def build_public_url(self, key: str) -> str:
        """
        Построить публичный URL (если объект public-read).

        Для Contabo US с кастомным PUBLIC_BASE_URL:
          CONTABO_S3_PUBLIC_BASE_URL="https://usc1.contabostorage.com/<storageName>:fadder"
        Итог: https://usc1.contabostorage.com/<storageName>:fadder/<key>
        """
        return f"{self.public_base_url}/{key}"


# ------- Инициализация singleton из settings / env -------

def _from_env(name: str, default: Optional[str] = None, required: bool = True) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing env var: {name}")
    return val  # type: ignore[return-value]


s3_service = S3Service(
    endpoint_url=settings.S3_CONTABO_ENDPOINT,
    access_key=settings.S3_CONTABO_ACCESS_KEY,
    secret_key=settings.S3_CONTABO_SECRET_KEY,
    bucket=settings.S3_CONTABO_BUCKET,
    region_name=settings.S3_CONTABO_REGION,
    addressing_style=settings.S3_CONTABO_ADDRESSING_STYLE,
    public_base_url=getattr(settings, "CONTABO_S3_PUBLIC_BASE_URL", None),
)
