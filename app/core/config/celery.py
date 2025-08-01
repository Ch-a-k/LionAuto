from celery import Celery
from app.core.config import settings
from json import JSONEncoder
from tortoise.models import Model

class TortoiseJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Model):
            return {**obj.__dict__, '_custom_serialized': True}
        return super().default(obj)
    
celery_app = Celery(
    'la_tasks',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.update(
    result_backend=settings.celery_result_backend,
    task_serializer='json',
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    accept_content=['json'],
    json_encoder=TortoiseJSONEncoder,
    result_extended=True,
    result_expires=3600, 
)

celery_app.autodiscover_tasks(["app.tasks"])
