import datetime
from typing import List, Optional

import pymongo
from odmantic.query import and_, desc
from pymongo.errors import PyMongoError

from ..models.transaction import Transaction, TransactionStatus


class TransactionRepository:
    def __init__(self, client: pymongo.MongoClient, db_name: str):
        self.db = client[db_name]
        self.mapping_class = Transaction
        self.collection_name = Transaction.__collection__
        self.collection = self.db[self.collection_name]

    def get_txs_between(
            self,
            start_time: datetime.datetime,
            end_time: datetime.datetime,
            status: TransactionStatus = None
    ) -> List[Transaction]:
        conditions = [
            Transaction.created_at >= start_time,
            Transaction.created_at <= end_time
        ]
        if status:
            conditions.append(Transaction.status == status)
        query = and_(*conditions)

        try:
            records = list(self.collection.find(filter=query))
        except PyMongoError as pme:
            raise Exception(f"Reading from mongodb failed: {pme}")
        return [self.mapping_class(**record) for record in records]

    def get_txs_last_24_hours(self, status: TransactionStatus = None) -> List[Transaction]:
        now = datetime.datetime.now()
        return self.get_txs_between(
            start_time=now - datetime.timedelta(days=1),
            end_time=now,
            status=status
        )

    def get_last_tx(self, wallet_address: str) -> Optional[Transaction]:
        query = and_(
            Transaction.wallet_address == wallet_address,
            Transaction.status == TransactionStatus.SUCCESS
        )
        try:
            result = self.collection.find_one(
                filter=query,
                sort=desc(Transaction.created_at),
            )
        except PyMongoError as pme:
            raise Exception(f"Reading from mongodb failed: {pme}")
        return self.mapping_class(**result) if result else None

    def write(self, tx: Transaction):
        try:
            self.collection.insert_one(document=tx.dict())
        except PyMongoError as pme:
            raise pme
