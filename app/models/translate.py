from tortoise import models, fields
import enum

class LanguageEnum(str, enum.Enum):
    RU = "ru"
    EN = "en"
    UA = "ua"
    MD = "md"
    KZ = "kz"
    PL = "pl"
    
    @classmethod
    def is_valid(cls, value):
        """
        Проверяет, является ли переданное значение допустимым кодом языка.
        """
        return value in cls._value2member_map_

class Translation(models.Model):
    id = fields.BigIntField(pk=True)
    field_name = fields.CharField(max_length=100)
    original_value = fields.CharField(max_length=100)
    translated_value = fields.CharField(max_length=100)
    language = fields.CharEnumField(LanguageEnum, max_length=10)

    class Meta:
        table = "translation"
        indexes = [
            ("field_name", "original_value", "language"),  # Индекс для быстрого поиска
        ]
        unique_together = [  # Добавляем уникальное ограничение
            ("field_name", "original_value", "language")
        ]