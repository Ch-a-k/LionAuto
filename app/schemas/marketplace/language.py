from pydantic import BaseModel, Field, ConfigDict

class LanguageCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=2, pattern=r"^[a-z]{2}$")

class LanguageRead(BaseModel):
    code: str

    model_config = ConfigDict(from_attributes=True)