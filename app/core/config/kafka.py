from app.core.config import settings

class KafkaConfig:
    @staticmethod
    def get_producer_config():
        return {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'message.max.bytes': 10000000,
            'queue.buffering.max.messages': 100000
        }

    @staticmethod
    def get_consumer_config(group_id: str = None):
        return {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'group.id': group_id or settings.KAFKA_GROUP_ID,
            'auto.offset.reset': settings.KAFKA_AUTO_OFFSET_RESET,
            'enable.auto.commit': settings.KAFKA_ENABLE_AUTO_COMMIT
        }