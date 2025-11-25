from enum import Enum


class NotificationChannel(str, Enum):
    in_app = "in_app"
    email = "email"
    sms = "sms"
    telegram = "telegram"
    whatsapp = "whatsapp"
