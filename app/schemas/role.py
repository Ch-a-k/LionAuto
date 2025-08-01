from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class PermissionSchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str]

class RoleSchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    permissions: List[PermissionSchema] = []
