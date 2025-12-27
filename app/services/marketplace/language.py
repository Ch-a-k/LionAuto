from app.models.marketplace.language import Language
from app.schemas.marketplace.language import LanguageCreate

async def create_language( LanguageCreate) -> Language:
    return await Language.create(code=data.code)

async def get_all_languages():
    return await Language.all()