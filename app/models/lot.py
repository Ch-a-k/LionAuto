from tortoise import fields, models
from typing import Optional
from loguru import logger
from tortoise.transactions import in_transaction
from tortoise.exceptions import IntegrityError
import re


def slugify(name: str) -> str:
        # Приводим к нижнему регистру
        name = name.lower().strip()

        # Заменяем все НЕ буквы и НЕ цифры на дефис
        name = re.sub(r'[^a-z0-9]+', '-', name)

        # Удаляем начальные и конечные дефисы
        name = name.strip('-')

        return name

class BaseReferenceModel(models.Model):
    """
    Базовая модель для справочных таблиц со `slug` и `name`.
    """
    id = fields.BigIntField(pk=True, auto_increment=True)
    slug = fields.CharField(max_length=100, unique=True)
    name = fields.CharField(max_length=100, unique=True)

    class Meta:
        abstract = True

    
    @classmethod
    async def get_or_create_by_name(cls, name: Optional[str], **kwargs) -> Optional['BaseReferenceModel']:
        """
        Получает или создает запись по имени. Если name=None, возвращает None.
        Если запись уже существует, возвращает существующую без попытки создания.
        """
        if not name:
            return None

        slug = slugify(name)
        filters = {"slug": slug}
        
        # Фильтрация по внешним ключам
        for k, v in kwargs.items():
            if isinstance(v, BaseReferenceModel):
                filters[f"{k}_id"] = v.id
            else:
                filters[k] = v

        # Пытаемся получить существующую запись
        instance = await cls.get_or_none(**filters)
        if instance:
            return instance

        # Пытаемся создать новую запись в отдельной транзакции
        try:
            async with in_transaction():
                data = {"slug": slug, "name": name}
                for k, v in kwargs.items():
                    if isinstance(v, BaseReferenceModel):
                        data[f"{k}_id"] = v.id
                    else:
                        data[k] = v

                instance = await cls.create(**data)
                return instance
        except IntegrityError as e:
            # Если возникла ошибка дубликата, просто возвращаем существующую запись
            logger.warning(f"Duplicate {cls.__name__} '{name}': {str(e)}. Returning existing record.")
            return await cls.get_or_none(**filters)
        except Exception as e:
            logger.error(f"Error creating {cls.__name__} '{name}': {str(e)}")
            return None

class VehicleType(BaseReferenceModel):
    """
    Тип транспортного средства (Automobile, Motorcycle, Truck)
    """
    icon_path = fields.CharField(max_length=255, null=True)
    icon_disable = fields.CharField(max_length=255, null=True, default='test')
    icon_active = fields.CharField(max_length=255, null=True, default='test')
    
    class Meta:
        table = "vehicle_type"

class Make(BaseReferenceModel):
    """
    Марка автомобиля (например, Lexus, Toyota)
    Принадлежит VehicleType (например, Automobile)
    """
    vehicle_type: fields.ForeignKeyRelation[VehicleType] = fields.ForeignKeyField(
        "models.VehicleType",
        related_name="makes",
        on_delete=fields.CASCADE
    )
    popular_counter = fields.IntField(null=False, index=True, default=0)
    icon_path = fields.CharField(max_length=255, null=True)
    
    class Meta:
        table = "make"
        unique_together = (("vehicle_type", "slug"), ("vehicle_type", "name"))

class Model(BaseReferenceModel):
    """
    Модель автомобиля, принадлежащая марке (например, RX для Lexus)
    """
    make: fields.ForeignKeyRelation[Make] = fields.ForeignKeyField(
        "models.Make", 
        related_name="models",
        on_delete=fields.CASCADE
    )
    
    class Meta:
        table = "model"
        unique_together = (("make", "slug"), ("make", "name"))

class Series(BaseReferenceModel):
    """
    Серия/поколение модели (например, RX350S для Lexus RX)
    """
    model: fields.ForeignKeyRelation[Model] = fields.ForeignKeyField(
        "models.Model",
        related_name="series",
        on_delete=fields.CASCADE
    )
    
    class Meta:
        table = "series"
        unique_together = (("model", "slug"), ("model", "name"))

class Status(BaseReferenceModel):
    hex = fields.CharField(max_length=7, null=True, default="#15b01a")
    letter = fields.CharField(max_length=7, null=True)
    description = fields.CharField(max_length=255, null=True)

class AuctionStatus(BaseReferenceModel):
    pass

class DamagePrimary(BaseReferenceModel):
    pass

class DamageSecondary(BaseReferenceModel):
    pass

class Keys(BaseReferenceModel):
    pass

class OdoBrand(BaseReferenceModel):
    pass

class Drive(BaseReferenceModel):
    pass

class Fuel(BaseReferenceModel):
    pass

class BodyType(BaseReferenceModel):
    pass

class Transmission(BaseReferenceModel):
    pass

class BaseSite(BaseReferenceModel):
    pass

class Title(BaseReferenceModel):
    pass

class SellerType(BaseReferenceModel):
    pass

class Seller(BaseReferenceModel):
    pass

class Document(BaseReferenceModel):
    pass

class DocumentOld(BaseReferenceModel):
    pass

class Color(BaseReferenceModel):
    hex = fields.CharField(max_length=7, null=True)

class PrefixIDModel(models.Model):
    """
    Базовый класс для моделей с префиксными ID
    """
    PREFIX = 0  # Базовый префикс, должен быть переопределен в дочерних классах
    
    @classmethod
    def get_next_id(cls, last_id: int = None) -> int:
        """Генерирует следующий ID с учетом префикса"""
        if last_id is None:
            return cls.PREFIX * 10_000_000 + 1  # Первый ID
        
        prefix = last_id // 10_000_000
        if prefix != cls.PREFIX:
            raise ValueError(f"ID prefix mismatch: expected {cls.PREFIX}, got {prefix}")
        
        return last_id + 1
    
    class Meta:
        abstract = True


class IDCounter(models.Model):
    """
    Таблица для хранения последних использованных ID для каждой таблицы
    """
    table_name = fields.CharField(max_length=50, unique=True)
    last_id = fields.BigIntField(default=0)
    
    class Meta:
        table = "id_counters"
    @classmethod
    async def get_last_shard_num(cls) -> int:
        """Возвращает номер последнего использованного шарда"""
        counter, _ = await cls.get_or_create(
            table_name="shard_counter",
            defaults={"last_id": 0}
        )
        return counter.last_id
    
    @classmethod
    async def set_last_shard_num(cls, shard_num: int) -> None:
        """Устанавливает номер последнего использованного шарда"""
        counter, _ = await cls.get_or_create(
            table_name="shard_counter",
            defaults={"last_id": 0}
        )
        counter.last_id = shard_num
        await counter.save()

    @classmethod
    async def initialize_counters(cls):
        """Инициализирует счетчики для всех таблиц при первом запуске"""
        tables = [
            ("Lot", 1),
            ("HistoricalLot", 2),
            ("LotWithoutAuctionDate", 3),
            ("LotWithouImage", 4),
            ("LotHistoryAddons", 5),
            ("LotOtherVehicle", 6)
        ]
        
        for table_name, prefix in tables:
            await cls.get_or_create(
                table_name=table_name,
                defaults={"last_id": prefix * 10_000_000}
            )
    
    @classmethod
    async def get_next_id(cls, table_name: str, shard_name: str = None) -> int:
        """
        Генерирует следующий ID для указанной таблицы и шарда
        :param table_name: Имя таблицы
        :param shard_name: Имя шарда (если None, используется основная таблица)
        :return: Следующий ID
        """
        counter_name = f"{table_name}_{shard_name}" if shard_name else table_name
        
        async with in_transaction():
            counter, created = await cls.get_or_create(
                table_name=counter_name,
                defaults={"last_id": cls.get_initial_id(table_name, shard_name)}
            )
            counter.last_id += 1
            await counter.save()
            return counter.last_id
    
    @staticmethod
    def get_initial_id(table_name: str, shard_name: str = None) -> int:
        """
        Возвращает начальный ID для таблицы/шарда
        """
        prefixes = {
            "Lot": 1,
            "HistoricalLot": 2,
            "LotWithoutAuctionDate": 3,
            "LotWithouImage": 4,
            "LotHistoryAddons": 5,
            "LotOtherVehicle": 6,
            "LotOtherVehicleHistorical": 7
        }
        
        prefix = prefixes.get(table_name, 0)
        shard_num = int(shard_name.replace("Lot", "")) if shard_name and shard_name != "Lot" else 0
        
        return prefix * 10_000_000 + shard_num * 1_000_000


class LotBase(PrefixIDModel):
    """
    Лот автомобиля на аукционе с полной иерархией VehicleType->Make->Model->Series
    """
    PREFIX = 0  # Базовый префикс, должен быть переопределен в дочерних классах

    @classmethod
    async def get_shard_for_new_record(cls) -> type['LotBase']:
        """
        Возвращает класс шарда для создания новой записи.
        Для нешардированных таблиц возвращает сам класс.
        Для шардированных таблиц выбирает шард по алгоритму.
        """
        # Если это не основной Lot, возвращаем текущий класс
        if cls != Lot:
            return cls
        
        # Алгоритм выбора шарда для основной таблицы Lot
        # Можно использовать round-robin, хеширование или другой метод
        # В этом примере используем простой round-robin
        
        # Получаем последний использованный шард из IDCounter
        last_shard_num = await IDCounter.get_last_shard_num()
        next_shard_num = (last_shard_num % 7) + 1  # У нас 7 шардов
        
        shard_classes = {
            1: Lot1,
            2: Lot2,
            3: Lot3,
            4: Lot4,
            5: Lot5,
            6: Lot6,
            7: Lot7
        }
        
        # Сохраняем номер последнего использованного шарда
        await IDCounter.set_last_shard_num(next_shard_num)
        
        return shard_classes[next_shard_num]
    
    @classmethod
    def get_shard_class(cls) -> type['LotBase']:
        """
        Возвращает класс шарда для текущей таблицы.
        Для базового класса возвращает None (должен быть переопределен в дочерних классах)
        """
        return None
    
    @classmethod
    async def get_all_shards(cls) -> list[type['LotBase']]:
        """
        Возвращает все классы шардов для текущего типа лота
        """
        if cls == Lot:
            return [Lot1, Lot2, Lot3, Lot4, Lot5, Lot6, Lot7]
        return [cls]
    
    @classmethod
    async def query_across_shards(cls, *args, **kwargs) -> list['LotBase']:
        """
        Выполняет запрос по всем шардам текущего типа и возвращает объединенный результат
        """
        results = []
        for shard_class in await cls.get_all_shards():
            results.extend(await shard_class.filter(*args, **kwargs))
        return results
    
    @classmethod
    async def query_across_shards_with_limit_offset(cls, limit: int = 18, offset: int = 0, *args, **kwargs) -> list['LotBase']:
        """
        Выполняет запрос по всем шардам текущего типа и возвращает объединенный результат с учетом общего лимита и оффсета.
        """
        results = []
        total_collected = 0
        remaining_offset = offset
        remaining_limit = limit

        for shard_class in await cls.get_all_shards():
            if remaining_limit <= 0:
                break

            # Считаем сколько записей всего в этом шарде (можно оптимизировать при необходимости)
            total_in_shard = await shard_class.filter(*args, **kwargs).count()

            if remaining_offset >= total_in_shard:
                remaining_offset -= total_in_shard
                continue

            shard_results = await shard_class.filter(*args, **kwargs)\
                .offset(remaining_offset)\
                .limit(remaining_limit)\
                .prefetch_related(
                    "make", "model", "vehicle_type", "damage_pr", "damage_sec",
                    "fuel", "drive", "transmission", "color", "status", "body_type",
                    "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
                )

            results.extend(shard_results)
            total_collected += len(shard_results)
            remaining_limit = limit - total_collected
            remaining_offset = 0  # Offset применяется только к первому подходящему шарду

        return results
    
    
    @classmethod
    async def get_min_max_odometer_across_shards(cls, *args, **kwargs) -> tuple[Optional[int], Optional[int]]:
        """
        Возвращает минимальный и максимальный одометр по всем шардам, учитывая переданные фильтры
        """
        min_odo = None
        max_odo = None

        for shard_class in await cls.get_all_shards():
            try:
                qs = shard_class.filter(*args, **kwargs)
                shard_min = await qs.order_by('odometer').limit(1).values_list('odometer', flat=True)
                shard_max = await qs.order_by('-odometer').limit(1).values_list('odometer', flat=True)

                if shard_min:
                    min_val = shard_min[0]
                    min_odo = min_val if min_odo is None else min(min_odo, min_val)

                if shard_max:
                    max_val = shard_max[0]
                    max_odo = max_val if max_odo is None else max(max_odo, max_val)
            except Exception as e:
                pass

        return min_odo, max_odo
    
    @classmethod
    async def count_across_shards(cls, *args, **kwargs) -> int:
        """
        Выполняет подсчет количества записей по всем шардам текущего типа
        """
        total = 0
        for shard_class in await cls.get_all_shards():
            try:
                count = await shard_class.filter(*args, **kwargs).count()
                if count:
                    total += count
            except Exception as e:
                pass
        return total
    
    @classmethod
    async def get_next_id(cls) -> int:
        """Генерирует следующий ID для текущей таблицы"""
        return await IDCounter.get_next_id(cls.__name__)
    
    async def save(self, *args, **kwargs):
        if not self.id:
            self.id = await self.__class__.get_next_id()
        await super().save(*args, **kwargs)
    
    @classmethod
    async def move_to(cls, source_id: int, target_class: type['LotBase']) -> 'LotBase':
        """
        Переносит лот в другую таблицу, сохраняя исходный ID
        Не обновляет счетчик, так как ID не меняется
        Возвращает новый экземпляр лота в целевой таблице
        """
        async with in_transaction() as connection:
            try:
                # Получаем исходный лот со всеми связями
                source_lot = await cls.get(id=source_id).prefetch_related(
                    *cls._meta.fk_fields,
                    *cls._meta.m2m_fields
                )
                
                # Проверяем существование ID в целевой таблице
                if await target_class.filter(id=source_id).exists():
                    raise ValueError(f"ID {source_id} already exists in target table")
                
                # Подготавливаем данные для переноса
                lot_data = {}
                for field_name in source_lot._meta.fields_map.keys():
                    if field_name == 'id':
                        continue
                        
                    field_value = getattr(source_lot, field_name)
                    
                    # Обрабатываем внешние ключи
                    if field_name in source_lot._meta.fk_fields:
                        if field_value:
                            field_value = await field_value
                    # Пропускаем M2M поля - они обрабатываются отдельно
                    elif field_name in source_lot._meta.m2m_fields:
                        continue
                        
                    lot_data[field_name] = field_value
                
                # Создаем новый лот в целевой таблице
                new_lot = target_class(id=source_id, **lot_data)
                await new_lot.save(using_db=connection)
                
                # Переносим M2M связи
                for field_name in source_lot._meta.m2m_fields:
                    m2m_values = await getattr(source_lot, field_name).all()
                    if m2m_values:
                        m2m_field = getattr(new_lot, field_name)
                        await m2m_field.add(*m2m_values, using_db=connection)
                
                # Удаляем исходный лот
                await source_lot.delete(using_db=connection)
                
                return new_lot
                
            except Exception as e:
                await connection.rollback()
                raise ValueError(f"Failed to move lot {source_id}: {str(e)}") from e
    
    # Убираем auto_increment=True, так как мы управляем ID вручную
    id = fields.BigIntField(pk=True)
    lot_id = fields.BigIntField(unique=True)
    odometer = fields.IntField(null=True, index=True)
    price = fields.FloatField(null=True, index=True)
    reserve_price = fields.FloatField(null=True)
    bid = fields.FloatField(index=True)
    current_bid = fields.FloatField(index=True)
    auction_date = fields.DatetimeField(null=True, index=True)
    cost_repair = fields.FloatField(null=True)
    year = fields.IntField(index=True)
    cylinders = fields.IntField(null=True)
    state = fields.CharField(max_length=10, index=True)

    # Иерархия транспортного средства
    vehicle_type = fields.ForeignKeyField(
        "models.VehicleType",
        null=True,
        on_delete=fields.SET_NULL,
    )
    make = fields.ForeignKeyField(
        "models.Make",
        null=True,
        on_delete=fields.SET_NULL,
    )
    model = fields.ForeignKeyField(
        "models.Model",
        null=True,
        on_delete=fields.SET_NULL,
    )
    series = fields.ForeignKeyField(
        "models.Series",
        null=True,
        on_delete=fields.SET_NULL,
    )

    # Остальные внешние ключи
    base_site = fields.ForeignKeyField(
        "models.BaseSite",
        null=True,
        on_delete=fields.SET_NULL,
    )
    damage_pr = fields.ForeignKeyField(
        "models.DamagePrimary",
        null=True,
        on_delete=fields.SET_NULL,
    )
    damage_sec = fields.ForeignKeyField(
        "models.DamageSecondary",
        null=True,
        on_delete=fields.SET_NULL,
    )
    keys = fields.ForeignKeyField(
        "models.Keys",
        null=True,
        on_delete=fields.SET_NULL,
    )
    odobrand = fields.ForeignKeyField(
        "models.OdoBrand",
        null=True,
        on_delete=fields.SET_NULL,
    )
    fuel = fields.ForeignKeyField(
        "models.Fuel",
        null=True,
        on_delete=fields.SET_NULL,
    )
    drive = fields.ForeignKeyField(
        "models.Drive",
        null=True,
        on_delete=fields.SET_NULL,
    )
    transmission = fields.ForeignKeyField(
        "models.Transmission",
        null=True,
        on_delete=fields.SET_NULL,
    )
    color = fields.ForeignKeyField(
        "models.Color",
        null=True,
        on_delete=fields.SET_NULL,
    )
    status = fields.ForeignKeyField(
        "models.Status",
        null=True,
        on_delete=fields.SET_NULL,
    )
    auction_status = fields.ForeignKeyField(
        "models.AuctionStatus",
        null=True,
        on_delete=fields.SET_NULL,
    )
    body_type = fields.ForeignKeyField(
        "models.BodyType",
        null=True,
        on_delete=fields.SET_NULL,
    )
    title = fields.ForeignKeyField(
        "models.Title",
        null=True,
        on_delete=fields.SET_NULL,
    )
    seller_type = fields.ForeignKeyField(
        "models.SellerType",
        null=True,
        on_delete=fields.SET_NULL,
    )
    seller = fields.ForeignKeyField(
        "models.Seller",
        null=True,
        on_delete=fields.SET_NULL,
    )
    document = fields.ForeignKeyField(
        "models.Document",
        null=True,
        on_delete=fields.SET_NULL,
    )
    document_old = fields.ForeignKeyField(
        "models.DocumentOld",
        null=True,
        on_delete=fields.SET_NULL,
    )

    # Детали лота
    vin = fields.CharField(max_length=50, unique=True)
    engine = fields.CharField(max_length=50, null=True)
    engine_size = fields.FloatField(null=True)
    location = fields.CharField(max_length=100)
    location_old = fields.CharField(max_length=100, null=True)
    country = fields.CharField(max_length=10, index=True)
    image_thubnail = fields.CharField(max_length=255, null=True)
    is_buynow = fields.BooleanField(index=True)
    link_img_hd = fields.JSONField()
    link_img_small = fields.JSONField()
    link = fields.CharField(max_length=255)
    risk_index = fields.FloatField(null=True, index=True)
    created_at = fields.DatetimeField(auto_now_add=True, index=True)
    updated_at = fields.DatetimeField(auto_now=True)
    is_historical = fields.BooleanField(index=True)

    class Meta:
        abstract = True
    

    async def set_vehicle_hierarchy(
        self,
        vehicle_type_name: str,
        make_name: str,
        model_name: Optional[str] = None,
        series_name: Optional[str] = None,
        year: Optional[int] = None
    ) -> None:
        """Устанавливает полную иерархию транспортного средства"""
        self.vehicle_type = await VehicleType.get_or_create_by_name(vehicle_type_name)
        
        if make_name:
            self.make = await Make.get_or_create_by_name(make_name)
            if self.make.vehicle_type_id != self.vehicle_type.id:
                self.make.vehicle_type = self.vehicle_type
                await self.make.save()
        
        if model_name and self.make:
            self.model = await Model.get_or_create_by_name(model_name)
            if self.model.make_id != self.make.id:
                self.model.make = self.make
                await self.model.save()
        
        if series_name and self.model:
            self.series = await Series.get_or_create_by_name(series_name)
            if self.series.model_id != self.model.id:
                self.series.model = self.model
                await self.series.save()
        
        await self.save()

    def get_vehicle_hierarchy(self) -> dict:
        """Возвращает полную иерархию транспортного средства"""
        return {
            "vehicle_type": self.vehicle_type.name if self.vehicle_type else None,
            "make": self.make.name if self.make else None,
            "model": self.model.name if self.model else None,
            "series": self.series.name if self.series else None,
            "year": self.year
        }


class Lot(LotBase):
    PREFIX = 10
    class Meta:
        table = "lot"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]

class Lot1(LotBase):
    PREFIX = 11
    class Meta:
        table = "lot1"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot2(LotBase):
    PREFIX = 12
    class Meta:
        table = "lot2"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot3(LotBase):
    PREFIX = 13
    class Meta:
        table = "lot3"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot4(LotBase):
    PREFIX = 14
    class Meta:
        table = "lot4"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot5(LotBase):
    PREFIX = 15
    class Meta:
        table = "lot5"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot6(LotBase):
    PREFIX = 16
    class Meta:
        table = "lot6"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class Lot7(LotBase):
    PREFIX = 17
    class Meta:
        table = "lot7"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("vehicle_type_id", "make_id", "model_id", "series_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
            ("make_id", "model_id"),
        ]


class HistoricalLot(LotBase):
    PREFIX = 2

    @classmethod
    async def historical_get_min_max_odometer(cls, *args, **kwargs) -> tuple[Optional[int], Optional[int]]:
        """
        Возвращает минимальный и максимальный одометр по таблице HistoricalLot, учитывая переданные фильтры.
        """
        try:
            qs = cls.filter(*args, **kwargs)

            min_odo_list = await qs.order_by('odometer').limit(1).values_list('odometer', flat=True)
            max_odo_list = await qs.order_by('-odometer').limit(1).values_list('odometer', flat=True)

            min_odo = min_odo_list[0] if min_odo_list else None
            max_odo = max_odo_list[0] if max_odo_list else None

            return min_odo, max_odo

        except Exception:
            return None, None

    @classmethod
    async def historical_count(cls, *args, **kwargs) -> int:
        """
        Выполняет подсчет количества записей в таблице HistoricalLot с учетом фильтров.
        """
        try:
            return await cls.filter(*args, **kwargs).count()
        except Exception:
            return 0
        
    @classmethod
    async def historical_query_with_limit_offset(
        cls,
        limit: int = 18,
        offset: int = 0,
        *args,
        **kwargs
    ) -> list['HistoricalLot']:
        """
        Выполняет запрос к таблице HistoricalLot с лимитом и оффсетом.
        """
        return await cls.filter(*args, **kwargs)\
            .offset(offset)\
            .limit(limit)\
            .prefetch_related(
                "make", "model", "vehicle_type", "damage_pr", "damage_sec",
                "fuel", "drive", "transmission", "color", "status", "body_type",
                "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
            )
    class Meta:
        table = "historical_lot"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]

class LotWithoutAuctionDate(LotBase):
    PREFIX = 3
    class Meta:
        table = "lot_without_auction_date"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]

class LotWithouImage(LotBase):
    PREFIX = 4
    class Meta:
        table = "lot_without_image"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]

class LotHistoryAddons(LotBase):
    PREFIX = 5
    vin = fields.CharField(max_length=50)
    class Meta:
        table = "lot_history_addons"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]


class LotOtherVehicle(LotBase):
    PREFIX = 6
    vin = fields.CharField(max_length=50)
    @classmethod
    async def other_vehicle_get_min_max_odometer(cls, *args, **kwargs) -> tuple[Optional[int], Optional[int]]:
        """
        Возвращает минимальный и максимальный одометр по таблице LotOtherVehicle, учитывая переданные фильтры.
        """
        try:
            qs = cls.filter(*args, **kwargs)

            min_odo_list = await qs.order_by('odometer').limit(1).values_list('odometer', flat=True)
            max_odo_list = await qs.order_by('-odometer').limit(1).values_list('odometer', flat=True)

            min_odo = min_odo_list[0] if min_odo_list else None
            max_odo = max_odo_list[0] if max_odo_list else None

            return min_odo, max_odo

        except Exception:
            return None, None

    @classmethod
    async def other_vehicle_count(cls, *args, **kwargs) -> int:
        """
        Выполняет подсчет количества записей в таблице LotOtherVehicle с учетом фильтров.
        """
        try:
            return await cls.filter(*args, **kwargs).count()
        except Exception:
            return 0
        
    @classmethod
    async def other_vehicle_query_with_limit_offset(
        cls,
        limit: int = 18,
        offset: int = 0,
        *args,
        **kwargs
    ) -> list['LotOtherVehicle']:
        """
        Выполняет запрос к таблице LotOtherVehicle с лимитом и оффсетом.
        """
        return await cls.filter(*args, **kwargs)\
            .offset(offset)\
            .limit(limit)\
            .prefetch_related(
                "make", "model", "vehicle_type", "damage_pr", "damage_sec",
                "fuel", "drive", "transmission", "color", "status", "body_type",
                "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
            )
    class Meta:
        table = "lot_vehicle_other"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]

class LotOtherVehicleHistorical(LotBase):
    PREFIX = 7
    vin = fields.CharField(max_length=50)
    @classmethod
    async def historical_other_vehicle_get_min_max_odometer(cls, *args, **kwargs) -> tuple[Optional[int], Optional[int]]:
        """
        Возвращает минимальный и максимальный одометр по таблице LotOtherVehicle, учитывая переданные фильтры.
        """
        try:
            qs = cls.filter(*args, **kwargs)

            min_odo_list = await qs.order_by('odometer').limit(1).values_list('odometer', flat=True)
            max_odo_list = await qs.order_by('-odometer').limit(1).values_list('odometer', flat=True)

            min_odo = min_odo_list[0] if min_odo_list else None
            max_odo = max_odo_list[0] if max_odo_list else None

            return min_odo, max_odo

        except Exception:
            return None, None

    @classmethod
    async def historical_other_vehicle_count(cls, *args, **kwargs) -> int:
        """
        Выполняет подсчет количества записей в таблице LotOtherVehicle с учетом фильтров.
        """
        try:
            return await cls.filter(*args, **kwargs).count()
        except Exception:
            return 0
        
    @classmethod
    async def historical_other_vehicle_query_with_limit_offset(
        cls,
        limit: int = 18,
        offset: int = 0,
        *args,
        **kwargs
    ) -> list['LotOtherVehicle']:
        """
        Выполняет запрос к таблице LotOtherVehicle с лимитом и оффсетом.
        """
        return await cls.filter(*args, **kwargs)\
            .offset(offset)\
            .limit(limit)\
            .prefetch_related(
                "make", "model", "vehicle_type", "damage_pr", "damage_sec",
                "fuel", "drive", "transmission", "color", "status", "body_type",
                "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
            )
    class Meta:
        table = "lot_vehicle_other_historical"
        indexes = [
            ("lot_id",),
            ("base_site", "auction_date"),
            ("make_id", "model_id"),
            ("year", "price"),
            ("state", "is_buynow"),
            ("vehicle_type_id", "body_type_id"),
            ("auction_date", "status_id"),
        ]


class LotRouter:
    """
    Роутер для определения в какой шард (таблицу) должен попасть лот
    """
    @staticmethod
    def get_shard_class(lot_id: int) -> type[LotBase]:
        """
        Возвращает класс шарда на основе ID лота
        """
        prefix = lot_id // 10_000_000
        
        # Определяем базовый класс на основе префикса
        if prefix == 1:
            base_class = Lot
        elif prefix == 2:
            return HistoricalLot
        elif prefix == 3:
            return LotWithoutAuctionDate
        elif prefix == 4:
            return LotWithouImage
        elif prefix == 5:
            return LotHistoryAddons
        elif prefix == 6:
            return LotOtherVehicle
        elif prefix == 7:
            return LotOtherVehicleHistorical
        else:
            raise ValueError(f"Unknown prefix: {prefix}")
        
        # Если это основной лот (префикс 1), распределяем по шардам
        if prefix == 1:
            shard_num = (lot_id % 10_000_000) % 7 + 1  # Распределение от 1 до 7
            shard_classes = {
                1: Lot1,
                2: Lot2,
                3: Lot3,
                4: Lot4,
                5: Lot5,
                6: Lot6,
                7: Lot7
            }
            return shard_classes[shard_num]
        
        return base_class

    @classmethod
    async def get_lot(cls, lot_id: int) -> Optional[LotBase]:
        """
        Получает лот из соответствующего шарда по ID
        """
        shard_class = cls.get_shard_class(lot_id)
        return await shard_class.get_or_none(id=lot_id)

    @classmethod
    async def create_lot(cls, lot_data: dict, lot_type: str = None) -> LotBase:
        """
        Создает новый лот в соответствующем шарде
        
        :param lot_data: Данные для создания лота
        :param lot_type: Тип лота (если None, определяется автоматически)
        :return: Созданный лот
        """
        if lot_type:
            # Создание лота определенного типа
            shard_classes = {
                'lot': Lot,
                'historical': HistoricalLot,
                'without_auction': LotWithoutAuctionDate,
                'without_image': LotWithouImage,
                'history_addon': LotHistoryAddons,
                'other_vehicle': LotOtherVehicle,
                'other_historical': LotOtherVehicleHistorical
            }
            shard_class = shard_classes.get(lot_type.lower(), Lot)
        else:
            # Автоматическое определение типа лота
            shard_class = Lot
        
        # Если это основной лот, выбираем случайный шард (или по другой логике)
        if shard_class == Lot:
            shard_num = (await IDCounter.get_next_id('Lot')) % 7 + 1
            shard_classes = {
                1: Lot1,
                2: Lot2,
                3: Lot3,
                4: Lot4,
                5: Lot5,
                6: Lot6,
                7: Lot7
            }
            shard_class = shard_classes[shard_num]
        
        lot = shard_class(**lot_data)
        await lot.save()
        return lot

    @classmethod
    async def move_lot(cls, source_id: int, target_type: str) -> LotBase:
        """
        Перемещает лот в другую таблицу (изменяет его тип)
        """
        source_lot = await cls.get_lot(source_id)
        if not source_lot:
            raise ValueError(f"Lot with ID {source_id} not found")
        
        target_classes = {
            'lot': Lot,
            'historical': HistoricalLot,
            'without_auction': LotWithoutAuctionDate,
            'without_image': LotWithouImage,
            'history_addon': LotHistoryAddons,
            'other_vehicle': LotOtherVehicle,
            'other_historical': LotOtherVehicleHistorical
        }
        
        target_class = target_classes.get(target_type.lower())
        if not target_class:
            raise ValueError(f"Unknown target type: {target_type}")
        
        return await source_lot.move_to(target_class)