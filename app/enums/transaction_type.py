from enum import Enum


class TransactionType(str, Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    bid_hold = "bid_hold"
    bid_release = "bid_release"
    bid_deduction = "bid_deduction"
    refund = "refund"
    fee = "fee"
    adjustment = "adjustment"
