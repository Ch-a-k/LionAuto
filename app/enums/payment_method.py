from enum import Enum


class PaymentMethod(str, Enum):
    bank_transfer = "bank_transfer"
    credit_card = "credit_card"
    debit_card = "debit_card"
    paypal = "paypal"
    crypto = "crypto"
    other = "other"
