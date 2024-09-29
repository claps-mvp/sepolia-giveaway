import datetime

from enum import Enum
from typing import Optional

from odmantic import Model


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class Transaction(Model):
    wallet_address: str
    transaction_id: Optional[str]
    amount: float
    status: TransactionStatus  # 'success' or 'failed'
    ip_address: str
    created_at: datetime.datetime
