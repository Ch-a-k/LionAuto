from tortoise import fields, models

class Language(models.Model):
    code = fields.CharField(max_length=2, pk=True)  # ru, en, pl

    class Meta:
        table = "languages"