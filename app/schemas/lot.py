from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Literal
from datetime import datetime

class FilterCounts(BaseModel):
    color: Optional[Dict[str, Dict[str, int]]] = None
    make: Optional[Dict[str, int]] = None
    body_class: Optional[Dict[str, int]] = None
    year: Optional[Dict[int, int]] = None
    transmission: Optional[Dict[str, int]] = None
    drive: Optional[Dict[str, int]] = None
    status: Optional[Dict[str, int]] = None
    condition_code: Optional[Dict[str, int]] = None
    damage1: Optional[Dict[str, int]] = None
    damage2: Optional[Dict[str, int]] = None
    auction: Optional[Dict[str, int]] = None
    displacement_l: Optional[Dict[float, int]] = None
    engine_cylinders: Optional[Dict[str, int]] = None
    lot_series: Optional[Dict[str, int]] = None
    odometer: Optional[Dict[int, int]] = None
    risk_index: Optional[Dict[str, int]] = None
    bid: Optional[Dict[float, int]] = None
    current_bid: Optional[Dict[float, int]] = None
    buy_it_now_price: Optional[Dict[float, int]] = None
    est_retail_value: Optional[Dict[float, int]] = None

class BaseReferenceModelValidation(BaseModel):
    id: int = Field(..., gt=0)
    slug: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)

class VehicleTypeModel(BaseReferenceModelValidation):
    icon_path: Optional[str] = ''
    icon_disable: Optional[str] = ''
    icon_active: Optional[str] = ''

class YearResponse(BaseModel):
    years: List[int]


class VehicleTypeModelAddons(BaseModel):
    id: int
    name: str
    slug: str
    counter: int = 0  # Add this field
    icon_path: str
    icon_disable: str
    icon_active: str

    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode

class MakeModelAddons(BaseModel):
    id: int
    name: str
    slug: str
    vehicle_type_id: int
    counter: int = 0  # Add this field
    
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode

class ModelModelAddons(BaseModel):
    id: int
    name: str
    slug: str
    make_id: int
    counter: int = 0  # Add this field
    
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode

class SeriesModelAddons(BaseModel):
    id: int
    name: str
    slug: str
    model_id: int
    counter: int = 0  # Add this field
    
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode

class YearResponseAddons(BaseModel):
    years: List[int]
    total_counter: int = 0  # Add this field
    
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode

class YearCountResponse(BaseModel):
    year: int
    counter: int

class StatusModel(BaseReferenceModelValidation):
    hex: Optional[str] = ''
    letter: Optional[str] = ''
    description: Optional[str] = ''

class AuctionStatusModel(BaseReferenceModelValidation):
    pass

class MakeModel(BaseReferenceModelValidation):
    popular_counter: Optional[int] = 0
    icon_path: Optional[str] = ''

class ModelModel(BaseReferenceModelValidation):
    pass

class DamagePrimaryModel(BaseReferenceModelValidation):
    pass

class DamageSecondaryModel(BaseReferenceModelValidation):
    pass

class KeysModel(BaseReferenceModelValidation):
    pass

class OdoBrandModel(BaseReferenceModelValidation):
    pass

class DriveModel(BaseReferenceModelValidation):
    pass

class FuelModel(BaseReferenceModelValidation):
    pass

class BodyTypeModel(BaseReferenceModelValidation):
    pass

class TransmissionModel(BaseReferenceModelValidation):
    pass

class BaseSite(BaseReferenceModelValidation):
    pass

class Series(BaseReferenceModelValidation):
    pass

class Title(BaseReferenceModelValidation):
    pass

class SellerType(BaseReferenceModelValidation):
    pass

class Seller(BaseReferenceModelValidation):
    pass

class Document(BaseReferenceModelValidation):
    pass

class DocumentOld(BaseReferenceModelValidation):
    pass

class ColorModel(BaseReferenceModelValidation):
    hex: str = Field(..., max_length=7)

class VehicleModel(BaseModel):
    # Основные поля
    lot_id: int = Field(..., gt=0, description="Unique lot identifier")
    base_site: str = Field(..., max_length=10)
    odometer: Optional[int] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)
    reserve_price: Optional[float] = Field(None, ge=0)
    bid: float = Field(0, ge=0)
    current_bid: float = Field(0, ge=0)
    auction_date: Optional[datetime] = None
    cost_repair: Optional[float] = Field(None, ge=0)
    year: int = Field(..., ge=1900, le=datetime.now().year)
    cylinders: Optional[int] = Field(None, ge=0)
    state: str = Field(..., max_length=10)
    
    # Связанные модели (теперь все поля Optional)
    vehicle_type: Optional[str] = Field(None)
    make: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    damage_pr: Optional[str] = Field(None)
    damage_sec: Optional[str] = Field(None)
    keys: Optional[str] = Field(None)
    odobrand: Optional[str] = Field(None)
    fuel: Optional[str] = Field(None)
    drive: Optional[str] = Field(None)
    transmission: Optional[str] = Field(None)
    color: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    auction_status: Optional[str] = Field(None)
    body_type: Optional[str] = Field(None)
    
    # Остальные поля
    series: Optional[str] = Field(None, max_length=100)
    title: str = Field(..., max_length=200)
    vin: str = Field(..., max_length=50)
    engine: Optional[str] = Field(None, max_length=50)
    engine_size: Optional[float] = Field(None, ge=0)
    location: str = Field(..., max_length=100)
    location_old: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., max_length=10)
    document: str = Field(..., max_length=50)
    document_old: Optional[str] = Field(None, max_length=100)
    seller: Optional[str] = Field(None, max_length=100)
    image_thubnail: Optional[str] = Field(None, max_length=255)
    is_buynow: bool = False
    link_img_hd: List[str] = Field(default_factory=list)
    link_img_small: List[str] = Field(default_factory=list)
    link: str = Field(..., max_length=255)
    seller_type: Optional[str] = Field(None, max_length=50)
    risk_index: Optional[float] = Field(None, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_historical: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        extra = "forbid"  # Запрещаем дополнительные поля

    @field_validator('vin')
    def validate_vin(cls, v):
        if len(v) != 17:
            raise ValueError('VIN must be exactly 17 characters')
        return v.upper()  # Приводим к верхнему регистру

    @field_validator('price', 'reserve_price', 'bid', 'current_bid', 'cost_repair', 'engine_size')
    def validate_positive_values(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value must be a positive number')
        return v
    
class VehicleModelOther(BaseModel):
    # Основные поля
    lot_id: int = Field(..., gt=0, description="Unique lot identifier")
    base_site: str = Field(..., max_length=10)
    odometer: Optional[int] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)
    reserve_price: Optional[float] = Field(None, ge=0)
    bid: float = Field(0, ge=0)
    current_bid: float = Field(0, ge=0)
    auction_date: Optional[datetime] = None
    cost_repair: Optional[float] = Field(None, ge=0)
    year: int = Field(..., ge=1900, le=datetime.now().year)
    cylinders: Optional[int] = Field(None, ge=0)
    state: str = Field(..., max_length=10)
    
    # Связанные модели (теперь все поля Optional)
    vehicle_type: Optional[str] = Field(None)
    make: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    damage_pr: Optional[str] = Field(None)
    damage_sec: Optional[str] = Field(None)
    keys: Optional[str] = Field(None)
    odobrand: Optional[str] = Field(None)
    fuel: Optional[str] = Field(None)
    drive: Optional[str] = Field(None)
    transmission: Optional[str] = Field(None)
    color: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    auction_status: Optional[str] = Field(None)
    body_type: Optional[str] = Field(None)
    
    # Остальные поля
    series: Optional[str] = Field(None, max_length=100)
    title: str = Field(..., max_length=200)
    vin: str = Field(..., max_length=50)
    engine: Optional[str] = Field(None, max_length=50)
    engine_size: Optional[float] = Field(None, ge=0)
    location: str = Field(..., max_length=100)
    location_old: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., max_length=10)
    document: str = Field(..., max_length=50)
    document_old: Optional[str] = Field(None, max_length=100)
    seller: Optional[str] = Field(None, max_length=100)
    image_thubnail: Optional[str] = Field(None, max_length=255)
    is_buynow: bool = False
    link_img_hd: List[str] = Field(default_factory=list)
    link_img_small: List[str] = Field(default_factory=list)
    link: str = Field(..., max_length=255)
    seller_type: Optional[str] = Field(None, max_length=50)
    risk_index: Optional[float] = Field(None, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_historical: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        extra = "forbid"  # Запрещаем дополнительные поля

    @field_validator('vin')
    def validate_vin(cls, v):
        return v.upper()  # Приводим к верхнему регистру

    @field_validator('price', 'reserve_price', 'bid', 'current_bid', 'cost_repair', 'engine_size')
    def validate_positive_values(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value must be a positive number')
        return v

class VehicleModelResponse(BaseModel):
    # Основные поля
    id: int = Field(..., gt=0, description="ID лота в базе")
    lot_id: int = Field(..., gt=0, description="Уникальный идентификатор лота")
    odometer: Optional[int] = Field(None, ge=0, description="Пробег")
    price: Optional[float] = Field(None, ge=0, description="Цена")
    reserve_price: Optional[float] = Field(None, ge=0, description="Резервная цена")
    bid: float = Field(0, ge=0, description="Текущая ставка")
    current_bid: float = Field(0, ge=0, description="Текущая ставка")
    auction_date: Optional[datetime] = Field(None, description="Дата аукциона")
    cost_repair: Optional[float] = Field(None, ge=0, description="Стоимость ремонта")
    year: int = Field(..., ge=1900, le=datetime.now().year, description="Год выпуска")
    cylinders: Optional[int] = Field(None, ge=0, description="Количество цилиндров")
    state: str = Field(..., description="Штат/регион")
    
    # Связанные модели (теперь возвращаются как полные объекты)
    base_site: Optional[BaseSite] = Field(None, description="Источник данных (copart/iaai)")
    vehicle_type: Optional[VehicleTypeModel] = Field(None, description="Тип транспортного средства")
    make: Optional[MakeModel] = Field(None, description="Марка")
    model: Optional[ModelModel] = Field(None, description="Модель")
    damage_pr: Optional[DamagePrimaryModel] = Field(None, description="Основные повреждения")
    damage_sec: Optional[DamageSecondaryModel] = Field(None, description="Вторичные повреждения")
    keys: Optional[KeysModel] = Field(None, description="Наличие ключей")
    odobrand: Optional[OdoBrandModel] = Field(None, description="Бренд одометра")
    fuel: Optional[FuelModel] = Field(None, description="Тип топлива")
    drive: Optional[DriveModel] = Field(None, description="Привод")
    transmission: Optional[TransmissionModel] = Field(None, description="Трансмиссия")
    color: Optional[ColorModel] = Field(None, description="Цвет")
    status: Optional[StatusModel] = Field(None, description="Статус")
    auction_status: Optional[AuctionStatusModel] = Field(None, description="Статус аукциона")
    body_type: Optional[BodyTypeModel] = Field(None, description="Тип кузова")
    series: Optional[Series] = Field(None, description="Серия")
    title: Optional[Title] = Field(..., description="Заголовок")
    seller: Optional[Seller] = Field(None, description="Продавец")
    seller_type: Optional[SellerType] = Field(None, description="Тип продавца")
    document: Optional[Document] = Field(..., description="Документ")
    document_old: Optional[DocumentOld] = Field(None, description="Предыдущий документ")
    
    # Остальные поля
    vin: str = Field(..., description="VIN-номер")
    engine: Optional[str] = Field(None, description="Двигатель")
    engine_size: Optional[float] = Field(None, ge=0, description="Объем двигателя")
    location: str = Field(..., description="Местоположение")
    location_old: Optional[str] = Field(None, description="Предыдущее местоположение")
    country: str = Field(..., description="Страна")
    image_thubnail: Optional[str] = Field(None, description="Миниатюра изображения")
    is_buynow: bool = Field(False, description="Доступно для немедленной покупки")
    link_img_hd: List[str] = Field(default_factory=list, description="Ссылки на HD изображения")
    link_img_small: List[str] = Field(default_factory=list, description="Ссылки на маленькие изображения")
    link: str = Field(..., description="Ссылка на лот")
    risk_index: Optional[float] = Field(None, ge=0, le=100, description="Индекс риска")
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления")
    is_historical: bool = Field(False, description="Исторические данные")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        from_attributes = True  # Для совместимости с ORM

    # Кастомные валидаторы
    @field_validator('vin')
    def validate_vin(cls, v):
        if len(v) != 17:
            raise ValueError('VIN must be exactly 17 characters')
        return v.upper()

    @field_validator('price', 'reserve_price', 'bid', 'current_bid', 'cost_repair', 'engine_size')
    def validate_positive_values(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value must be a positive number')
        return v

    @classmethod
    def from_orm_with_relations(cls, db_lot):
        """Создает ответ из ORM объекта с полными связанными моделями"""
        lot_data = {
            **db_lot.__dict__,
            'vehicle_type': VehicleTypeModel.model_validate(db_lot.vehicle_type) if db_lot.vehicle_type else None,
            'make': MakeModel.model_validate(db_lot.make) if db_lot.make else None,
            'model': ModelModel.model_validate(db_lot.model) if db_lot.model else None,
            'damage_pr': DamagePrimaryModel.model_validate(db_lot.damage_pr) if db_lot.damage_pr else None,
            'damage_sec': DamageSecondaryModel.model_validate(db_lot.damage_sec) if db_lot.damage_sec else None,
            'keys': KeysModel.model_validate(db_lot.keys) if db_lot.keys else None,
            'odobrand': OdoBrandModel.model_validate(db_lot.odobrand) if db_lot.odobrand else None,
            'fuel': FuelModel.model_validate(db_lot.fuel) if db_lot.fuel else None,
            'drive': DriveModel.model_validate(db_lot.drive) if db_lot.drive else None,
            'transmission': TransmissionModel.model_validate(db_lot.transmission) if db_lot.transmission else None,
            'color': ColorModel.model_validate(db_lot.color) if db_lot.color else None,
            'status': StatusModel.model_validate(db_lot.status) if db_lot.status else None,
            'auction_status': AuctionStatusModel.model_validate(db_lot.auction_status) if db_lot.auction_status else None,
            'body_type': BodyTypeModel.model_validate(db_lot.body_type) if db_lot.body_type else None,
            'series': Series.model_validate(db_lot.series) if db_lot.series else None,
            'title': Title.model_validate(db_lot.title) if db_lot.title else None,
            'seller_type': SellerType.model_validate(db_lot.seller_type) if db_lot.seller_type else None,
            'seller': Seller.model_validate(db_lot.seller) if db_lot.seller else None,
            'document': Document.model_validate(db_lot.document) if db_lot.document else None,
            'document_old': DocumentOld.model_validate(db_lot.document_old) if db_lot.document_old else None,
            'base_site': BaseSite.model_validate(db_lot.base_site) if db_lot.base_site else None,
        }   
        return cls.model_validate(lot_data)

class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[List[VehicleModelResponse]] = None  # This is the list of results

class LotResponseModel(BaseModel):
    status: Optional[bool] = None
    message: Optional[str] = None
    lot_id: Optional[int] = None
    id: Optional[int] = None

class TaskResponseModel(BaseModel):
    status: Optional[bool] = None
    message: Optional[str] = None
    task_id: Optional[str] = None

class BatchTaskResponse(BaseModel):
    task_id: str
    total_lots: int
    message: str = "Партия лотов принята в обработку"

class LotResult(BaseModel):
    vin: str
    status: str  # "success" | "failed"
    error: Optional[str] = None
    lot_id: Optional[int] = None

class BatchTaskStatus(BaseModel):
    task_id: str
    status: str  # "PENDING" | "PROGRESS" | "COMPLETED" | "FAILED"
    processed: int
    success: int
    failed: int
    results: List[LotResult] = []

class TaskResponse(BaseModel):
    task_id: str
    message: str

class TaskRefineResponse(BaseModel):
    lots: Optional[List] = None
    count: int = 0
    stats: Optional[FilterCounts] = None

class LotTypeCount(BaseModel):
    count: int

class LotSearchResponse(BaseModel):
    id: int
    lot_id: int
    image_thubnail: str
    make: str
    model: str
    year: int
    lot_series: str
    vin: str
    auction: str

class LotMarkResponse(BaseModel):
    slug: str
    name: str
    icon: str

class LotHistoryItem(BaseModel):
    id: int
    lot_id: int
    sale_datetime: Optional[datetime] = None
    auction_date: Optional[datetime] = None
    auction: str
    image_thubnail: str
    odometer: int
    bid: float
    current_bid: float
    final_bid: float
    status: str
    color: str
    seller: str
    seller_type: str
    is_historical: bool = False

class LotHistoryResponse(BaseModel):
    last_bid: float
    last_auction_date: Optional[datetime] = None
    data: Optional[List[LotHistoryItem]] = []



SpecialFilterLiteral = Literal[
        "buy_now","keys","minimum_odometer",
        "maximum_odometer","document_clean","auction_date_today",
        "auction_date_tomorrow","auction_next_week", "run-and-drive"
        ]