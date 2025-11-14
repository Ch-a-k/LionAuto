from tortoise import models, fields

class Lead(models.Model):
    id = fields.IntField(pk=True)
    phone = fields.CharField(max_length=20)  # Для номера телефона
    name = fields.CharField(max_length=100, null=True)  # Необязательное имя
    
    body_class = fields.CharField(max_length=50, null=True)
    year = fields.CharField(max_length=10, null=True)
    budget = fields.CharField(max_length=50, null=True)
    email = fields.CharField(max_length=100, null=True)
    comment = fields.TextField(null=True)
    
    utm_source = fields.CharField(max_length=100, null=True)
    utm_medium = fields.CharField(max_length=100, null=True)
    utm_campaign = fields.CharField(max_length=100, null=True)
    utm_term = fields.CharField(max_length=100, null=True)
    utm_content = fields.CharField(max_length=100, null=True)
    status = fields.CharField(max_length=100, null=True)
    
    client_id = fields.CharField(max_length=50, null=True)
    
    created_at = fields.DatetimeField(auto_now_add=True)  # Добавим дату создания
    
    class Meta:
        table = "leads"