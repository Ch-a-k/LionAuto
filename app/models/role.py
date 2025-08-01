from tortoise import fields, models
from uuid import uuid4

class Role(models.Model):
    id = fields.UUIDField(pk=True, default=uuid4)
    name = fields.CharField(max_length=50, unique=True)
    description = fields.TextField(null=True)

    permissions: fields.ManyToManyRelation["Permission"] = fields.ManyToManyField(
        "models.Permission", related_name="roles", through="role_permissions"
    )

    class Meta:
        table = "roles"

class Permission(models.Model):
    id = fields.UUIDField(pk=True, default=uuid4)
    name = fields.CharField(max_length=50, unique=True)
    description = fields.TextField(null=True)

    roles: fields.ManyToManyRelation[Role]

    class Meta:
        table = "permissions"
