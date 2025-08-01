from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID

from app.models.role import Role, Permission
from app.schemas.role import RoleSchema, PermissionSchema
from app.api.dependencies import get_current_admin_user

router = APIRouter()

# Роли

@router.get("/", response_model=List[RoleSchema])
async def list_roles(current_user=Depends(get_current_admin_user)):
    roles = await Role.all().prefetch_related("permissions")
    return roles

@router.post("/", response_model=RoleSchema, status_code=status.HTTP_201_CREATED)
async def create_role(role_in: RoleSchema, current_user=Depends(get_current_admin_user)):
    role = await Role.create(name=role_in.name, description=role_in.description)
    return role

@router.get("/{role_id}", response_model=RoleSchema)
async def get_role(role_id: UUID, current_user=Depends(get_current_admin_user)):
    role = await Role.get_or_none(id=role_id).prefetch_related("permissions")
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.put("/{role_id}", response_model=RoleSchema)
async def update_role(role_id: UUID, role_in: RoleSchema, current_user=Depends(get_current_admin_user)):
    role = await Role.get_or_none(id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    role.name = role_in.name
    role.description = role_in.description
    await role.save()
    return role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, current_user=Depends(get_current_admin_user)):
    role = await Role.get_or_none(id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    await role.delete()
    return

# Управление правами для роли

@router.post("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_permission_to_role(role_id: UUID, permission_id: UUID, current_user=Depends(get_current_admin_user)):
    role = await Role.get_or_none(id=role_id)
    permission = await Permission.get_or_none(id=permission_id)
    if not role or not permission:
        raise HTTPException(status_code=404, detail="Role or Permission not found")
    await role.permissions.add(permission)
    return

@router.delete("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(role_id: UUID, permission_id: UUID, current_user=Depends(get_current_admin_user)):
    role = await Role.get_or_none(id=role_id)
    permission = await Permission.get_or_none(id=permission_id)
    if not role or not permission:
        raise HTTPException(status_code=404, detail="Role or Permission not found")
    await role.permissions.remove(permission)
    return

# CRUD для Permissions

@router.get("/permissions", response_model=List[PermissionSchema])
async def list_permissions(current_user=Depends(get_current_admin_user)):
    permissions = await Permission.all()
    return permissions

@router.post("/permissions", response_model=PermissionSchema, status_code=status.HTTP_201_CREATED)
async def create_permission(permission_in: PermissionSchema, current_user=Depends(get_current_admin_user)):
    permission = await Permission.create(name=permission_in.name, description=permission_in.description)
    return permission

@router.get("/permissions/{permission_id}", response_model=PermissionSchema)
async def get_permission(permission_id: UUID, current_user=Depends(get_current_admin_user)):
    permission = await Permission.get_or_none(id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission

@router.put("/permissions/{permission_id}", response_model=PermissionSchema)
async def update_permission(permission_id: UUID, permission_in: PermissionSchema, current_user=Depends(get_current_admin_user)):
    permission = await Permission.get_or_none(id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission.name = permission_in.name
    permission.description = permission_in.description
    await permission.save()
    return permission

@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(permission_id: UUID, current_user=Depends(get_current_admin_user)):
    permission = await Permission.get_or_none(id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    await permission.delete()
    return
