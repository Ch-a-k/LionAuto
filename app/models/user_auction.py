from tortoise import fields, models
import uuid
from app.core.security.encryption import encrypt, decrypt
from app.enums.auction_type import AuctionType

class UserAuctionAccount(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="auction_accounts")
    auction_type = fields.CharEnumField(AuctionType)
    username_encrypted = fields.CharField(max_length=255)
    password_encrypted = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    last_successful_login = fields.DatetimeField(null=True)
    account_status = fields.CharField(max_length=20, default="active")

    class Meta:
        table = "user_auction_accounts"
        unique_together = (("user", "auction_type"),)

    @classmethod
    async def create_encrypted(cls, user, auction_type, username: str, password: str):
        username_enc = encrypt(username)  # строка на вход
        password_enc = encrypt(password)
        return await cls.create(
            user=user,
            auction_type=auction_type,
            username_encrypted=username_enc,
            password_encrypted=password_enc,
        )

    def get_decrypted_credentials(self):
        username = decrypt(self.username_encrypted)  # decrypt возвращает строку
        password = decrypt(self.password_encrypted)
        return username, password
