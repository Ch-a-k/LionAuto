# app/models/audit_log.py
from tortoise import fields, models
from app.enums.audit_action import AuditAction

class CustomerAuditLog(models.Model):
    customer = fields.ForeignKeyField("models.Customer", related_name="audit_logs")
    action = fields.CharEnumField(AuditAction)
    details = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "customer_audit_logs"