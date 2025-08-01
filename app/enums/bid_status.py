from enum import Enum

class BidStatus(str, Enum):
    pending = "pending"
    placed = "placed"
    outbid = "outbid"
    won = "won"
    failed = "failed"
    cancelled = "cancelled"
