from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from app.schemas.common import PaginatedResponse

# --- Вложенные элементы ---
class AttributeInput(BaseModel):
    attribute_type_code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z_]+$")
    language_code: str = Field(..., min_length=2, max_length=2, pattern=r"^[a-z]{2}$")
    value: str = Field(..., min_length=1)

class ColorInput(BaseModel):
    color_type_code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z_]+$")
    language_code: str = Field(..., min_length=2, max_length=2, pattern=r"^[a-z]{2}$")
    color_name: str = Field(..., min_length=1, max_length=100)


# --- Основные схемы ---
class CarModelCreate(BaseModel):
    brand_id: int
    model_name: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1900, le=2030)
    length_mm: Optional[int] = None
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    wheelbase_mm: Optional[int] = None
    attributes: List[AttributeInput] = Field(default_factory=list)
    colors: List[ColorInput] = Field(default_factory=list)


class CarModelDetailRead(BaseModel):
    id: int
    brand_id: int
    brand_name: str
    model_name: str
    year: int
    length_mm: int | None
    width_mm: int | None
    height_mm: int | None
    wheelbase_mm: int | None
    slogan: str | None
    engine: str | None
    fuel_type: str | None
    drive_type: str | None
    transmission: str | None
    suspension: str | None
    interior: str | None
    body_colors: str | None     # "Black, White"
    interior_colors: str | None # "Beige, Red"
    image_paths: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class CarModelListResponse(PaginatedResponse[CarModelDetailRead]):
    pass