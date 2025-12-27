from app.models.marketplace.model import CarModel
from app.models.marketplace.translation import ModelAttribute, ModelColor
from app.models.marketplace.attribute import AttributeType
from app.models.marketplace.color import ColorType
from app.models.marketplace.brand import Brand
from app.models.marketplace.language import Language
from app.schemas.marketplace.model import CarModelCreate
from tortoise.exceptions import DoesNotExist
from tortoise import Tortoise
from tortoise.transactions import in_transaction

# --- CREATE ---
async def create_car_model(data: CarModelCreate) -> CarModel:
    brand = await Brand.get_or_none(id=data.brand_id)
    if not brand:
        raise ValueError("Brand not found")

    all_lang_codes = {attr.language_code for attr in data.attributes} | {color.language_code for color in data.colors}
    if all_lang_codes:
        valid_langs = set(await Language.all().values_list("code", flat=True))
        invalid = all_lang_codes - valid_langs
        if invalid:
            raise ValueError(f"Unsupported language codes: {', '.join(invalid)}")

    model = await CarModel.create(
        brand=brand,
        model_name=data.model_name,
        year=data.year,
        length_mm=data.length_mm,
        width_mm=data.width_mm,
        height_mm=data.height_mm,
        wheelbase_mm=data.wheelbase_mm,
    )

    # Атрибуты 
    for attr in data.attributes:
        attr_type = await AttributeType.get_or_none(code=attr.attribute_type_code)
        if not attr_type:
            raise ValueError(f"Unknown attribute type: {attr.attribute_type_code}")
        await ModelAttribute.create(
            model=model,
            attribute_type=attr_type,
            language_code=attr.language_code,
            value=attr.value
        )

    # Цвета 
    for color in data.colors:
        color_type = await ColorType.get_or_none(code=color.color_type_code)
        if not color_type:
            raise ValueError(f"Unknown color type: {color.color_type_code}")
        await ModelColor.create(
            model=model,
            color_type=color_type,
            language_code=color.language_code,
            color_name=color.color_name
        )

    return model


async def delete_car_models(model_ids: list[int]) -> int:
    if not model_ids:
        return 0

    async with in_transaction():
        # Удаляем модели — каскадно удалятся атрибуты и цвета
        deleted_count = await CarModel.filter(id__in=model_ids).delete()
        return deleted_count

async def update_car_model(model_id: int, data: CarModelCreate) -> CarModel:
    async with in_transaction():
        # Проверка существования модели
        model = await CarModel.get_or_none(id=model_id)
        if not model:
            raise ValueError("Model not found")
        
        # Проверка бренда
        brand = await Brand.get_or_none(id=data.brand_id)
        if not brand:
            raise ValueError("Brand not found")

        # Валидация языков
        all_lang_codes = {attr.language_code for attr in data.attributes} | {color.language_code for color in data.colors}
        if all_lang_codes:
            valid_langs = set(await Language.all().values_list("code", flat=True))
            invalid = all_lang_codes - valid_langs
            if invalid:
                raise ValueError(f"Unsupported language codes: {', '.join(invalid)}")

        # Обновление основной модели
        await CarModel.filter(id=model_id).update(
            brand=brand,
            model_name=data.model_name,
            year=data.year,
            length_mm=data.length_mm,
            width_mm=data.width_mm,
            height_mm=data.height_mm,
            wheelbase_mm=data.wheelbase_mm,
        )

        # Удаляем ВСЕ старые переводы
        await ModelAttribute.filter(model_id=model_id).delete()
        await ModelColor.filter(model_id=model_id).delete()

        # Создаём новые атрибуты
        for attr in data.attributes:
            attr_type = await AttributeType.get_or_none(code=attr.attribute_type_code)
            if not attr_type:
                raise ValueError(f"Unknown attribute type: {attr.attribute_type_code}")
            await ModelAttribute.create(
                model_id=model_id,
                attribute_type=attr_type,
                language_code=attr.language_code,
                value=attr.value
            )

        # Создаём новые цвета
        for color in data.colors:
            color_type = await ColorType.get_or_none(code=color.color_type_code)
            if not color_type:
                raise ValueError(f"Unknown color type: {color.color_type_code}")
            await ModelColor.create(
                model_id=model_id,
                color_type=color_type,
                language_code=color.language_code,
                color_name=color.color_name
            )

        return await CarModel.get(id=model_id)


async def get_models_with_translations(
    lang: str = "en",
    brand_id: int | None = None,
    year: int | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 10
):
    offset = (page - 1) * size

    # Формируем WHERE
    where_clauses = []
    params = [lang]
    param_index = 2

    if brand_id:
        where_clauses.append(f"m.brand_id = ${param_index}")
        params.append(brand_id)
        param_index += 1
    if year:
        where_clauses.append(f"m.year = ${param_index}")
        params.append(year)
        param_index += 1
    if search:
        where_clauses.append(f"(m.model_name ILIKE ${param_index} OR b.name ILIKE ${param_index})")
        params.append(f"%{search}%")
        param_index += 1

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Добавляем LIMIT/OFFSET параметры
    params.extend([size, offset])
    limit_offset = f"LIMIT ${len(params)-1} OFFSET ${len(params)}"

    query = f"""
    WITH
    slogans AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'slogan')
        GROUP BY model_id
    ),
    engines AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'engine')
        GROUP BY model_id
    ),
    fuel_types AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'fuel_type')
        GROUP BY model_id
    ),
    drive_types AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'drive_type')
        GROUP BY model_id
    ),
    transmissions AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'transmission')
        GROUP BY model_id
    ),
    suspensions AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'suspension')
        GROUP BY model_id
    ),
    interiors_attrs AS (
        SELECT model_id, jsonb_object_agg(language_code, value) AS translations
        FROM model_attributes
        WHERE attribute_type_id = (SELECT id FROM attribute_types WHERE code = 'interior')
        GROUP BY model_id
    ),
    body_colors AS (
        SELECT
            model_id,
            jsonb_object_agg(language_code, color_list) AS translations
        FROM (
            SELECT
                model_id,
                language_code,
                string_agg(color_name, ', ' ORDER BY color_name) AS color_list
            FROM model_colors
            WHERE color_type_id = (SELECT id FROM color_types WHERE code = 'body')
            GROUP BY model_id, language_code
        ) AS grouped
        GROUP BY model_id
    ),
    interior_colors AS (
        SELECT
            model_id,
            jsonb_object_agg(language_code, color_list) AS translations
        FROM (
            SELECT
                model_id,
                language_code,
                string_agg(color_name, ', ' ORDER BY color_name) AS color_list
            FROM model_colors
            WHERE color_type_id = (SELECT id FROM color_types WHERE code = 'interior')
            GROUP BY model_id, language_code
        ) AS grouped
        GROUP BY model_id
    ),
    total_count AS (
        SELECT COUNT(*) AS total
        FROM models m
        JOIN brands b ON m.brand_id = b.id
        {where_sql}
    )
    SELECT
        m.id,
        m.brand_id,
        b.name AS brand_name,
        m.model_name,
        m.year,
        m.length_mm,
        m.width_mm,
        m.height_mm,
        m.wheelbase_mm,
        COALESCE(s.translations->>$1, s.translations->>'en') AS slogan,
        COALESCE(e.translations->>$1, e.translations->>'en') AS engine,
        COALESCE(ft.translations->>$1, ft.translations->>'en') AS fuel_type,
        COALESCE(dt.translations->>$1, dt.translations->>'en') AS drive_type,
        COALESCE(tr.translations->>$1, tr.translations->>'en') AS transmission,
        COALESCE(susp.translations->>$1, susp.translations->>'en') AS suspension,
        COALESCE(ia.translations->>$1, ia.translations->>'en') AS interior,
        COALESCE(bc.translations->>$1, bc.translations->>'en') AS body_colors,
        COALESCE(ic.translations->>$1, ic.translations->>'en') AS interior_colors,
        (SELECT total FROM total_count) AS total
    FROM models m
    JOIN brands b ON m.brand_id = b.id
    LEFT JOIN slogans s ON s.model_id = m.id
    LEFT JOIN engines e ON e.model_id = m.id
    LEFT JOIN fuel_types ft ON ft.model_id = m.id
    LEFT JOIN drive_types dt ON dt.model_id = m.id
    LEFT JOIN transmissions tr ON tr.model_id = m.id
    LEFT JOIN suspensions susp ON susp.model_id = m.id
    LEFT JOIN interiors_attrs ia ON ia.model_id = m.id
    LEFT JOIN body_colors bc ON bc.model_id = m.id
    LEFT JOIN interior_colors ic ON ic.model_id = m.id
    {where_sql}
    ORDER BY b.name, m.model_name
    {limit_offset}
    """

    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(query, params)

    if not rows:
        return [], 0

    total = rows[0]["total"]
    return rows, total