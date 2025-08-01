# app/enums/audit_action.py
from enum import Enum

class AuditAction(str, Enum):
    DOCUMENT_UPLOAD = "document_upload"
    STATUS_CHANGE = "status_change"
    PROFILE_UPDATE = "profile_update"
    VERIFICATION = "verification"