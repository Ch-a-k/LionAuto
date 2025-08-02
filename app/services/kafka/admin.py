from confluent_kafka.admin import AdminClient, NewTopic
from app.core.config.kafka import KafkaConfig
from loguru import logger

class KafkaAdmin:
    def __init__(self):
        self.admin_client = AdminClient({'bootstrap.servers': KafkaConfig.get_producer_config()['bootstrap.servers']})

    def create_topics(self):
        topics = [
            # Доменные топики
            NewTopic("auction.bids.created", num_partitions=3, replication_factor=1),
            NewTopic("auction.bids.updated", num_partitions=3, replication_factor=1),
            NewTopic("auction.lots.created", num_partitions=3, replication_factor=1),
            NewTopic("auction.lots.updated", num_partitions=3, replication_factor=1),

            # Внешние (Copart)
            NewTopic("auction.copart.raw", num_partitions=3, replication_factor=1),
            NewTopic("auction.copart.normalized", num_partitions=3, replication_factor=1),
            NewTopic("auction.copart.alerts", num_partitions=3, replication_factor=1),

            # Системные
            NewTopic("auction.system.alerts", num_partitions=1, replication_factor=1),
            NewTopic("auction.user.notifications", num_partitions=1, replication_factor=1),

            NewTopic("auction.lot.watch_updates", num_partitions=3, replication_factor=1),
        ]

        fs = self.admin_client.create_topics(topics)

        for topic, f in fs.items():
            try:
                f.result()  # Ждём завершения создания
                logger.info(f"Topic {topic} created")
            except Exception as e:
                logger.error(f"Failed to create topic {topic}: {e}")
