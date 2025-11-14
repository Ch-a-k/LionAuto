from typing import Literal, Dict
from pydantic import BaseModel

TransLiteral = Literal["ru", "en", "md", "ua", "kz", "pl"]


class TranslationUpdateRequest(BaseModel):
    """
    Модель для запроса обновления перевода.
    """
    field_name: str
    original_value: str
    translations: Dict[str, str]