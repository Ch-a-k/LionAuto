from loguru import logger
from app.models import BaseReferenceModel, LanguageEnum, Translation
from typing import Type, Dict, Optional

async def create_model_translations(rel_name, model_instance: Type[BaseReferenceModel]) -> None:
    """
    Создает переводы для всех языков для указанной модели.
    Использует slug модели как ключ для переводов.
    
    :param model_instance: Экземпляр модели, для которой нужно создать переводы
    """
    if not model_instance or not model_instance.slug:
        return
    
    try:
        # Используем имя модели как поле для перевода
        model_name = model_instance.__class__.__name__.lower()  # Получаем имя модели в нижнем регистре, например, "damagepr"
        translation_key = model_instance.slug
        model_name_value = model_instance.name  # Сохраняем название модели для перевода
        
        # Проходим по всем языкам из LanguageEnum и создаем переводы
        for language in LanguageEnum:
            # Проверяем существование перевода для данного языка
            existing_translation = await Translation.filter(
                field_name=rel_name,  # Здесь будет имя модели
                original_value=translation_key,  # Используем slug как ключ
                language=language
            ).first()
            
            if not existing_translation:
                # Если это английский язык, то переводом будет имя модели
                translated_value = model_name_value if language == LanguageEnum.EN else ""
                
                # Создаем запись в таблице переводов
                await Translation.create(
                    field_name=rel_name,  # Сохраняем имя модели как поле
                    original_value=translation_key,  # Сохраняем slug как оригинальное значение
                    translated_value=translated_value,  # Перевод
                    language=language  # Указываем язык
                )
    except Exception as e:
        logger.error(f"Error creating translations for model '{model_instance.__class__.__name__}': {str(e)}")


async def get_translations(
    field_name: str,
    original_values: list[str],
    language: LanguageEnum
) -> Dict[str, str]:
    """
    Получает переводы для списка оригинальных значений по указанному полю и языку.
    
    :param field_name: Название поля (например, 'vehicle_type')
    :param original_values: Список оригинальных значений для перевода
    :param language: Язык перевода
    :return: Словарь {original_value: translated_value}
    """
    if not original_values:
        return {}
    
    # Получаем все переводы для указанных параметров одним запросом
    translations = await Translation.filter(
        field_name=field_name,
        original_value__in=original_values,
        language=language
    )
    
    # Создаем словарь для быстрого поиска
    return {t.original_value: t.translated_value for t in translations}


async def get_translation(
    field_name: str,
    original_value: str,
    language: LanguageEnum
) -> Optional[str]:
    """
    Получает перевод для одного оригинального значения по указанному полю и языку.
    
    :param field_name: Название поля (например, 'vehicle_type')
    :param original_value: Оригинальное значение для перевода
    :param language: Язык перевода
    :return: Переведенное значение или None, если перевод не найден
    """
    translation = await Translation.filter(
        field_name=field_name,
        original_value=original_value,
        language=language
    ).first()
    
    return translation.translated_value if translation else None