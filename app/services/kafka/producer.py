from confluent_kafka import Producer
from app.core.config.kafka import KafkaConfig
from loguru import logger

class KafkaProducer:
    def __init__(self):
        # Инициализация клиента с конфигом из KafkaConfig
        self.producer = Producer(KafkaConfig.get_producer_config())

    def delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def produce(self, topic: str, value: str, key: str = None):
        # Отправка сообщения с колбеком на delivery_report
        self.producer.produce(
            topic=topic,
            key=key,
            value=value,
            callback=self.delivery_report
        )
        # Принудительный вызов poll для обработки callback-ов
        self.producer.poll(0)

    def flush(self):
        # Ожидает отправки всех сообщений
        self.producer.flush()

# Глобальный объект для переиспользования продюсера во всем проекте
kafka_producer = KafkaProducer()
