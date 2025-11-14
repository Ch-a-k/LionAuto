from tortoise import Tortoise
from tortoise.transactions import in_transaction
from loguru import logger
from app.core.config import settings
from app.models import *
from app.core.security.security import get_password_hash
from app.schemas.user import Permissions
from app.models import Lot, LotBase
from typing import Optional
from tortoise.exceptions import ConfigurationError
import types

async def create_default_roles():
    """Создает стандартные роли системы"""
    default_roles = [
        {
            "name": "superadmin",
            "description": "Полный доступ ко всем функциям",
            "permissions": [Permissions.FULL_ACCESS.value]
        },
        {
            "name": "admin",
            "description": "Администратор системы",
            "permissions": [
                Permissions.DASHBOARD.value,
                Permissions.USERS.value,
                Permissions.TRANSACTIONS.value,
                Permissions.CALCULATOR.value
            ]
        },
        {
            "name": "manager",
            "description": "Менеджер по работе с клиентами",
            "permissions": [
                Permissions.DASHBOARD.value,
                Permissions.LEADS.value,
                Permissions.AUTO_LOTS.value
            ]
        }
    ]
    
    for role_data in default_roles:
        await CalculatorRole.get_or_create(
            name=role_data["name"],
            defaults={
                "description": role_data["description"],
                "permissions": role_data["permissions"]
            }
        )

async def create_admin_user():
    """Создает администратора по умолчанию"""
    if not all([settings.first_superuser_email, settings.first_superuser_password]):
        logger.warning("Не указаны учетные данные администратора в настройках")
        return

    if await CalculatorUser.exists(email=settings.first_superuser_email):
        return

    admin_role = await CalculatorRole.get(name="superadmin")
    await CalculatorUser.create(
        username="admin",
        email=settings.first_superuser_email,
        password_hash=get_password_hash(settings.first_superuser_password),
        full_name="Администратор системы",
        position="Администратор",
        phone="+10000000000",
        is_active=True,
        role=admin_role
    )

# async def get_lot_from_shard(lot_id: int) -> Optional[LotShardManager]:
#     # Получаем имя таблицы для шардирования
#     shard_name = LotShardManager.get_shard_name(lot_id)
#     logger.debug(f"Selected shard: {shard_name}")

#     # Получаем модель для этого шарда из зарегистрированных моделей
#     number_shard = shard_name.split('_')[-1]
#     logger.debug(Tortoise.apps.get("models"))
#     LotModel: LotBase = Tortoise.apps.get("models")[f"LotShard{number_shard}"]
#     if LotModel:
#         # Используем эту модель для выполнения запроса
#         return LotModel
#     else:
#         logger.error(f"Sharded model {shard_name} not found.")
#         return None

async def create_additional_information():
    try:
        tables = [
            ("lot", 1),          # Основные лоты (будет шардироваться)
            ("historical_lot", 2),
            ("lot_without_auction_date", 3),
            ("lot_without_image", 4),
            ("lot_history_addons", 5),
            ("lot_vehicle_other", 6),
            ("lot_vehicle_other_historical", 7)
        ]
        
        # Шарды для основной таблицы lot
        lot_shards = [
            ("lot1", 11),
            ("lot2", 12),
            ("lot3", 13),
            ("lot4", 14),
            ("lot5", 15),
            ("lot6", 16),
            ("lot7", 17)
        ]

        async with in_transaction() as connection:
            # Вставка дефолтных данных, если нужно
            count = await Lot.all().count()
            if count == 0:
                with open('migrations/insert_translation.sql', 'r') as f:
                    translation_sql = f.read()
                    await connection.execute_script(translation_sql)
                
                # Инициализация последовательностей для основных таблиц
                for table in tables:
                    table_name, prefix = table[0], table[1]
                    await connection.execute_script(
                        f"ALTER SEQUENCE IF EXISTS {table_name}_id_seq RESTART WITH {prefix}0000001;"
                    )
                    logger.info(f'Initialized sequence for {table_name} with prefix: {prefix}')
                
                # Инициализация последовательностей для шардов
                for shard in lot_shards:
                    shard_name, prefix = shard[0], shard[1]
                    await connection.execute_script(
                        f"ALTER SEQUENCE IF EXISTS {shard_name}_id_seq RESTART WITH {prefix}0000001;"
                    )
                    logger.info(f'Initialized sequence for shard {shard_name} with prefix: {prefix}')
                
                # Инициализация счетчиков в IDCounter
                await IDCounter.initialize_counters()

            await connection.execute_script("""
                INSERT INTO color (slug, name, hex) VALUES
                ('blue', 'Blue', '#0343df'),
                ('grey', 'Grey', '#929591'),
                ('black', 'Black', '#000000'),
                ('orange', 'Orange', '#f97306'),
                ('turquoise', 'Turquoise', '#06c2ac'),
                ('yellow', 'Yellow', '#ffff14'),
                ('charcoal', 'Charcoal', '#343837'),
                ('silver', 'Silver', '#c5c9c7'),
                ('white', 'White', '#ffffff'),
                ('other', 'Other', '#FF5733'),
                ('green', 'Green', '#15b01a'),
                ('red', 'Red', '#e50000'),
                ('brown', 'Brown', '#653700'),
                ('purple', 'Purple', '#7e1e9c'),
                ('gold', 'Gold', '#dbb40c'),
                ('pink', 'Pink', '#ff81c0'),
                ('beige', 'Beige', '#F5F5DC'),
                ('two-colors', 'Two Colors', '#FF5733')
                ON CONFLICT (slug) DO NOTHING;
            """)

            await connection.execute_script("""
                INSERT INTO status (slug, name, hex, letter, description)
                VALUES
                    ('run-and-drive', 'Run & Drive', '#15b01a', 'R', ''),
                    ('unknown', 'Unknown', '#FFA500', 'U', ''),
                    ('stationary', 'Stationary', '#ADD8E6', 'S', ''),
                    ('starts', 'Starts', '#00008B', 'S', '')
                ON CONFLICT (slug) DO NOTHING;
            """)
            await connection.execute_script("""
                INSERT INTO vehicle_type (slug, name, icon_path) VALUES
                    ('atvs', 'ATVs', 'https://www.svgrepo.com/show/183699/quad.svg'),
                    ('jet-skis', 'Jet Skis', 'https://www.svgrepo.com/show/8712/jet-ski.svg'),
                    ('motorcycle', 'Motorcycles', 'https://www.svgrepo.com/show/433608/motorcycle-f.svg'),
                    ('snowmobile', 'Snowmobile', 'https://www.svgrepo.com/show/222449/snowmobile.svg'),
                    ('pickup-trucks', 'Pickup Trucks', 'https://www.svgrepo.com/show/252972/pickup-truck.svg'),
                    ('special-equipment', 'Special equipment', 'https://www.svgrepo.com/show/352591/tractor.svg'),
                    ('medium-duty-box-trucks', 'Medium Duty/Box Trucks', 'https://www.svgrepo.com/show/480852/truck-delivery.svg'),
                    ('dirt-bikes', 'Dirt Bikes', 'https://www.svgrepo.com/show/490080/dirt-bike.svg'),
                    ('trailers', 'Trailers', 'https://www.svgrepo.com/show/308359/trailer-travel-outdoors-nature.svg'),
                    ('rv', 'RV', 'https://www.svgrepo.com/show/490042/camper.svg'),
                    ('boats', 'Boats', 'https://www.svgrepo.com/show/243342/sailing-boat-boat.svg'),
                    ('automobile', 'Automobile', 'https://www.svgrepo.com/show/243249/automobile-car.svg'),
                    ('heavy-duty-trucks', 'Heavy Duty Trucks', 'https://www.svgrepo.com/show/183663/truck.svg'),
                    ('bus', 'Bus', 'https://www.svgrepo.com/show/513182/bus.svg')
                ON CONFLICT (slug) DO NOTHING;
            """)
            await connection.execute_script("""
                INSERT INTO translation (field_name, original_value, translated_value, language) VALUES
                    ('vehicle_type', 'atvs', 'ATVs', 'en'),
                    ('vehicle_type', 'atvs', 'Внедорожники', 'ru'),
                    ('vehicle_type', 'atvs', 'Позашляховики', 'ua'),
                    ('vehicle_type', 'atvs', 'ATV', 'md'),
                    ('vehicle_type', 'atvs', 'ATV', 'kz'),
                    ('vehicle_type', 'atvs', 'ATV', 'pl'),

                    ('vehicle_type', 'jet-skis', 'Jet Skis', 'en'),
                    ('vehicle_type', 'jet-skis', 'Гидроциклы', 'ru'),
                    ('vehicle_type', 'jet-skis', 'Гідроцикли', 'ua'),
                    ('vehicle_type', 'jet-skis', 'Гідроцикли', 'md'),
                    ('vehicle_type', 'jet-skis', 'Гидроциклы', 'kz'),
                    ('vehicle_type', 'jet-skis', 'Skuter wodny', 'pl'),

                    ('vehicle_type', 'motorcycle', 'Motorcycles', 'en'),
                    ('vehicle_type', 'motorcycle', 'Мотоциклы', 'ru'),
                    ('vehicle_type', 'motorcycle', 'Мотоцикли', 'ua'),
                    ('vehicle_type', 'motorcycle', 'Motoare', 'md'),
                    ('vehicle_type', 'motorcycle', 'Мотоцикли', 'kz'),
                    ('vehicle_type', 'motorcycle', 'Motocykle', 'pl'),

                    ('vehicle_type', 'snowmobile', 'Snowmobile', 'en'),
                    ('vehicle_type', 'snowmobile', 'Снегоходы', 'ru'),
                    ('vehicle_type', 'snowmobile', 'Снігоходи', 'ua'),
                    ('vehicle_type', 'snowmobile', 'Ski-doo', 'md'),
                    ('vehicle_type', 'snowmobile', 'Снегоходы', 'kz'),
                    ('vehicle_type', 'snowmobile', 'Skuter śnieżny', 'pl'),

                    ('vehicle_type', 'pickup-trucks', 'Pickup Trucks', 'en'),
                    ('vehicle_type', 'pickup-trucks', 'Пикапы', 'ru'),
                    ('vehicle_type', 'pickup-trucks', 'Пікапи', 'ua'),
                    ('vehicle_type', 'pickup-trucks', 'Pikape', 'md'),
                    ('vehicle_type', 'pickup-trucks', 'Пикапы', 'kz'),
                    ('vehicle_type', 'pickup-trucks', 'Pojazdy dostawcze', 'pl'),

                    ('vehicle_type', 'special-equipment', 'Special Equipment', 'en'),
                    ('vehicle_type', 'special-equipment', 'Специальная техника', 'ru'),
                    ('vehicle_type', 'special-equipment', 'Спеціальна техніка', 'ua'),
                    ('vehicle_type', 'special-equipment', 'Echipamente speciale', 'md'),
                    ('vehicle_type', 'special-equipment', 'Арнайы техника', 'kz'),
                    ('vehicle_type', 'special-equipment', 'Specjalistyczne maszyny', 'pl'),

                    ('vehicle_type', 'medium-duty-box-trucks', 'Medium Duty/Box Trucks', 'en'),
                    ('vehicle_type', 'medium-duty-box-trucks', 'Грузовики средней нагрузки', 'ru'),
                    ('vehicle_type', 'medium-duty-box-trucks', 'Вантажівки середнього класу', 'ua'),
                    ('vehicle_type', 'medium-duty-box-trucks', 'Camioane de dimensiuni medii', 'md'),
                    ('vehicle_type', 'medium-duty-box-trucks', 'Грузовики среднего класса', 'kz'),
                    ('vehicle_type', 'medium-duty-box-trucks', 'Ciężarówki średniej wielkości', 'pl'),

                    ('vehicle_type', 'dirt-bikes', 'Dirt Bikes', 'en'),
                    ('vehicle_type', 'dirt-bikes', 'Внедорожные мотоциклы', 'ru'),
                    ('vehicle_type', 'dirt-bikes', 'Кросові мотоцикли', 'ua'),
                    ('vehicle_type', 'dirt-bikes', 'Motociclete off-road', 'md'),
                    ('vehicle_type', 'dirt-bikes', 'Внедорожные мотоциклы', 'kz'),
                    ('vehicle_type', 'dirt-bikes', 'Motocykle terenowe', 'pl'),

                    ('vehicle_type', 'trailers', 'Trailers', 'en'),
                    ('vehicle_type', 'trailers', 'Прицепы', 'ru'),
                    ('vehicle_type', 'trailers', 'Причепи', 'ua'),
                    ('vehicle_type', 'trailers', 'Remorci', 'md'),
                    ('vehicle_type', 'trailers', 'Прицепы', 'kz'),
                    ('vehicle_type', 'trailers', 'Przyczepy', 'pl'),

                    ('vehicle_type', 'rv', 'RV', 'en'),
                    ('vehicle_type', 'rv', 'Дом на колесах', 'ru'),
                    ('vehicle_type', 'rv', 'Кемпінгові автомобілі', 'ua'),
                    ('vehicle_type', 'rv', 'Autocare', 'md'),
                    ('vehicle_type', 'rv', 'Автодома', 'kz'),
                    ('vehicle_type', 'rv', 'Kamper', 'pl'),

                    ('vehicle_type', 'boats', 'Boats', 'en'),
                    ('vehicle_type', 'boats', 'Лодки', 'ru'),
                    ('vehicle_type', 'boats', 'Човни', 'ua'),
                    ('vehicle_type', 'boats', 'Bărci', 'md'),
                    ('vehicle_type', 'boats', 'Лодки', 'kz'),
                    ('vehicle_type', 'boats', 'Łodzie', 'pl'),

                    ('vehicle_type', 'automobile', 'Automobile', 'en'),
                    ('vehicle_type', 'automobile', 'Автомобили', 'ru'),
                    ('vehicle_type', 'automobile', 'Автомобілі', 'ua'),
                    ('vehicle_type', 'automobile', 'Automobile', 'md'),
                    ('vehicle_type', 'automobile', 'Автомобили', 'kz'),
                    ('vehicle_type', 'automobile', 'Samochody', 'pl'),

                    ('vehicle_type', 'heavy-duty-trucks', 'Heavy Duty Trucks', 'en'),
                    ('vehicle_type', 'heavy-duty-trucks', 'Грузовики тяжелого класса', 'ru'),
                    ('vehicle_type', 'heavy-duty-trucks', 'Вантажівки важкого класу', 'ua'),
                    ('vehicle_type', 'heavy-duty-trucks', 'Camioane de mare tonaj', 'md'),
                    ('vehicle_type', 'heavy-duty-trucks', 'Грузовики тяжелого класса', 'kz'),
                    ('vehicle_type', 'heavy-duty-trucks', 'Ciężarówki o dużym tonażu', 'pl'),

                    ('vehicle_type', 'bus', 'Bus', 'en'),
                    ('vehicle_type', 'bus', 'Автобус', 'ru'),
                    ('vehicle_type', 'bus', 'Автобус', 'ua'),
                    ('vehicle_type', 'bus', 'Autobuz', 'md'),
                    ('vehicle_type', 'bus', 'Автобус', 'kz'),
                    ('vehicle_type', 'bus', 'Autobus', 'pl')
                ON CONFLICT DO NOTHING;
            """)
            logger.info("All default data inserted with if exist parameters!")
    except Exception as e:
        print(e)


async def init_db():
    """Initialize database with all models"""
    await Tortoise.init(
        db_url=settings.database_url,
        modules={'models': ['app.models']}
    )
    
    try:
        await Tortoise.generate_schemas(safe=True)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


async def close_db():
    """Close database connections"""
    await Tortoise.close_connections()