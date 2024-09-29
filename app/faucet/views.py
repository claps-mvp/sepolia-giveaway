import datetime
import logging
from typing import Optional

from pymongo import MongoClient
from rest_framework import views, status
from rest_framework.response import Response
from web3 import Web3

from .data.models.transaction import Transaction, TransactionStatus
from .data.repositories.transaction_repository import TransactionRepository
from .serializers import FundSerializer
from app import settings

logger = logging.getLogger(__name__)

web3 = Web3(
    Web3.HTTPProvider(settings.RPC_URL)
)
if web3.is_connected():
    logger.info("Connected to Sepolia via RPC!")
else:
    logger.info(f"Connection failed to {settings.RPC_URL}")

client = MongoClient(settings.MONGO_URI, maxPoolSize=50)
tx_repository = TransactionRepository(client=client, db_name=settings.DB_NAME)


class FundView(views.APIView):

    def post(self, request) -> Response:
        logger.info(f"Received fund request with payload: {request.data}")
        serializer = FundSerializer(data=request.data)

        if not serializer.is_valid():
            return self._invalid_request(serializer)

        wallet_address = serializer.validated_data["wallet_address"]
        ip_address = request.META.get("REMOTE_ADDR")
        logger.info(f"Request validated. Wallet: {wallet_address}, IP: {ip_address}")

        if self._is_rate_limited(wallet_address=wallet_address, ip_address=ip_address):
            return self._rate_limit_exceeded(wallet_address=wallet_address, ip_address=ip_address)

        return self._process_funding(wallet_address, ip_address)

    @classmethod
    def _invalid_request(cls, serializer: FundSerializer) -> Response:
        logger.error(f"Invalid request data: {serializer.errors}")
        return Response(
            {"error": f"Invalid data: {serializer.errors}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @classmethod
    def _is_rate_limited(cls, wallet_address: str, ip_address: str) -> bool:
        last_tx = tx_repository.get_last_tx(wallet_address=wallet_address, ip_address=ip_address)
        if last_tx:
            time_since_last_tx = (datetime.datetime.now() - last_tx.created_at).total_seconds()
            if time_since_last_tx < settings.FUNDING_COOLDOWN:
                return True
        return False

    def _rate_limit_exceeded(self, wallet_address: str, ip_address: str) -> Response:
        transaction = self._create_transaction(
            wallet_address=wallet_address,
            txn_status=TransactionStatus.FAILED,
            ip_address=ip_address,
            amount=0,
            txn_hash=None
        )
        tx_repository.write(transaction)
        logger.warning(f"Rate limit exceeded for wallet: {wallet_address}, IP: {ip_address}")
        return Response(
            {"error": "Rate limit exceeded. Please wait before requesting again."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def _process_funding(self, wallet_address: str, ip_address: str) -> Response:
        try:
            txn_hash = self._create_and_send_transaction(wallet_address)
            transaction = self._create_transaction(
                wallet_address=wallet_address,
                txn_status=TransactionStatus.SUCCESS,
                ip_address=ip_address,
                amount=settings.GIVEAWAY_VALUE,
                txn_hash=txn_hash.hex()
            )
            tx_repository.write(transaction)
            logger.info(f"Transaction successful. ID: {txn_hash.hex()}")
            return Response({"transaction_id": txn_hash.hex()}, status=status.HTTP_200_OK)
        except Exception as e:
            return self._handle_funding_error(wallet_address, ip_address, str(e))

    @classmethod
    def _create_and_send_transaction(cls, wallet_address: str):
        wallet = web3.to_checksum_address(settings.WALLET_ADDRESS)
        nonce = web3.eth.get_transaction_count(wallet, 'pending')
        txn = {
            "nonce": nonce,
            "to": wallet_address,
            "value": web3.to_wei(settings.GIVEAWAY_VALUE, "ether"),
            "gas": settings.DEFAULT_GAS,
            "gasPrice": web3.to_wei("20", "gwei"),
        }
        signed_txn = web3.eth.account.sign_transaction(txn, private_key=settings.WALLET_PK)
        logger.info(f"Signed transaction for wallet {wallet_address}: {signed_txn}")
        txn_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        logger.info(f"Transaction hash: {txn_hash.hex()}")
        return txn_hash

    @classmethod
    def _create_transaction(
            cls,
            wallet_address: str,
            txn_status: str,
            ip_address: str,
            amount: float,
            txn_hash: Optional[str]
    ):
        return Transaction(
            wallet_address=wallet_address,
            transaction_id=txn_hash,
            amount=amount,
            status=txn_status,
            ip_address=ip_address,
            created_at=datetime.datetime.now(),
        )

    def _handle_funding_error(self, wallet_address: str, ip_address: str, error: str) -> Response:
        transaction = self._create_transaction(
            wallet_address=wallet_address,
            txn_status=TransactionStatus.FAILED,
            ip_address=ip_address,
            amount=0,
            txn_hash=None
        )
        tx_repository.write(transaction)
        logger.error(f"Transaction failed for wallet: {wallet_address}. Error: {error}")
        return Response(
            {"error": f"Transaction failed: {error}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StatsView(views.APIView):
    def get(self, request) -> Response:
        try:
            success_count = len(tx_repository.get_txs_last_24_hours(status=TransactionStatus.SUCCESS))
            failed_count = len(tx_repository.get_txs_last_24_hours(status=TransactionStatus.FAILED))

            logger.info(f"Stats fetched successfully. Success count: {success_count}, Failed count: {failed_count}")
            return Response({"num_success": success_count, "num_failed": failed_count})
        except Exception as e:
            logger.error("Error fetching stats: %s", str(e))
            return Response(
                {"error": f"Unable to fetch stats: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
