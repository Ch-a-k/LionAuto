from tortoise import fields, models

class BotSession(models.Model):
    """
    Храним Playwright storage_state для конкретного username.
    PK = username (уникальный логин/идентификатор).
    """
    username: str = fields.CharField(pk=True, max_length=255)
    storage_state_json = fields.JSONField()
    # в SQLite хранится как TEXT, но это ок; auto_now авто-обновляет при save()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "bot_sessions"  # совпадает с твоей таблицей
