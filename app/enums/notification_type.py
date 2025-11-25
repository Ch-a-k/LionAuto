from enum import Enum


class NotificationType(str, Enum):
    info = "info"
    success = "success"
    warning = "warning"
    error = "error"
    bid_placed = "bid_placed"
    bid_won = "bid_won"
    bid_lost = "bid_lost"
    deposit_received = "deposit_received"
    deposit_failed = "deposit_failed"
    kyc_approved = "kyc_approved"
    kyc_rejected = "kyc_rejected"
    auction_reminder = "auction_reminder"
    two_fa_enabled = "two_fa_enabled"
    two_fa_disabled = "two_fa_disabled"
