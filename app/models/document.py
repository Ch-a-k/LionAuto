from tortoise import fields, models
from app.enums.document_type import DocumentType

class CustomerDocument(models.Model):
    customer = fields.ForeignKeyField("models.Customer", related_name="documents")
    type = fields.CharEnumField(DocumentType)
    s3_path = fields.CharField(max_length=512)
    is_approved = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "customer_documents"