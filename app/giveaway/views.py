import datetime
import logging

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
    Web3.HTTPProvider(f"https://sepolia.infura.io/v3/{settings.INFURA_PROJECT_ID}")
)
if web3.is_connected():
    logger.info("Connected to Sepolia via Infura!")
else:
    logger.info(f"Connection failed to https://sepolia.infura.io/v3/{settings.INFURA_PROJECT_ID}")

client = MongoClient(settings.MONGO_URI, maxPoolSize=50)
tx_repository = TransactionRepository(client=client, db_name=settings.DB_NAME)


class FundView(views.APIView):
    def post(self, request) -> Response:
        logger.info("Received fund request with payload: %s", request.data)
        serializer = FundSerializer(data=request.data)

        if serializer.is_valid():
            wallet_address = serializer.validated_data["wallet_address"]
            ip_address = request.META.get("REMOTE_ADDR")
            logger.info(
                "Request validated. Wallet: %s, IP: %s", wallet_address, ip_address
            )

            # Check rate limit
            last_tx = tx_repository.get_last_tx(wallet_address=wallet_address)
            if (
                last_tx
                and (datetime.datetime.now() - last_tx.created_at).total_seconds()
                < settings.FUNDING_COOLDOWN
            ):
                transaction = Transaction(
                    wallet_address=wallet_address,
                    transaction_id=None,
                    amount=0,
                    status=TransactionStatus.FAILED,
                    ip_address=ip_address,
                    created_at=datetime.datetime.now(),
                )
                tx_repository.write(transaction)
                logger.warning(
                    "Rate limit exceeded for wallet: %s, IP: %s",
                    wallet_address,
                    ip_address,
                )
                return Response(
                    {
                        "error": "Rate limit exceeded. Please wait before requesting again."
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Fund Transaction
            try:
                logger.info(
                    "Initiating fund transaction for wallet: %s", wallet_address
                )
                wallet = web3.to_checksum_address(settings.WALLET_ADDRESS)
                nonce = web3.eth.get_transaction_count(wallet, 'pending')
                txn = {
                    "nonce": nonce,
                    "to": wallet_address,
                    "value": web3.to_wei(settings.GIVEAWAY_VALUE, "ether"),
                    "gas": settings.DEFAULT_GAS,
                    "gasPrice": web3.to_wei("20", "gwei"),
                }
                signed_txn = web3.eth.account.sign_transaction(
                    txn, private_key=settings.WALLET_PK
                )
                txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

                # Save successful transaction
                transaction = Transaction(
                    wallet_address=wallet_address,
                    transaction_id=txn_hash.hex(),
                    amount=settings.GIVEAWAY_VALUE,
                    status=TransactionStatus.SUCCESS,
                    ip_address=ip_address,
                    created_at=datetime.datetime.now(),
                )
                tx_repository.write(transaction)
                logger.info("Transaction successful. ID: %s", txn_hash.hex())

                return Response(
                    {"transaction_id": txn_hash.hex()}, status=status.HTTP_200_OK
                )
            except Exception as e:
                # Save failed transaction
                transaction = Transaction(
                    wallet_address=wallet_address,
                    transaction_id=None,
                    amount=0,
                    status=TransactionStatus.FAILED,
                    ip_address=ip_address,
                    created_at=datetime.datetime.now(),
                )
                tx_repository.write(transaction)
                logger.error(
                    "Transaction failed for wallet: %s. Error: %s",
                    wallet_address,
                    str(e),
                )

                return Response(
                    {"error": f"Transaction failed: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            logger.error("Invalid request data: %s", serializer.errors)
            return Response(
                {"error": f"Invalid data: {serializer.errors}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class StatsView(views.APIView):
    def get(self, request) -> Response:
        try:
            success_count = len(tx_repository.get_txs_last_24_hours(status=TransactionStatus.SUCCESS))
            failed_count = len(tx_repository.get_txs_last_24_hours(status=TransactionStatus.FAILED))

            logger.info(
                "Stats fetched successfully. Success count: %d, Failed count: %d",
                success_count,
                failed_count,
            )
            return Response({"num_success": success_count, "num_failed": failed_count})
        except Exception as e:
            logger.error("Error fetching stats: %s", str(e))
            return Response(
                {"error": f"Unable to fetch stats: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
