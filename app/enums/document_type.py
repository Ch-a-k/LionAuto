# app/enums/document_type.py
from enum import Enum

class DocumentType(str, Enum):
    PASSPORT = "passport"
    ID_CARD = "id_card"
    DRIVER_LICENSE = "driver_license"
    SELFIE = "selfie"
    UTILITY_BILL = "utility_bill"