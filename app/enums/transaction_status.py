from enum import Enum


class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    reversed = "reversed"
