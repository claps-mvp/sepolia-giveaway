from rest_framework import serializers


class FundSerializer(serializers.Serializer):
    wallet_address = serializers.CharField(max_length=42, required=True)
