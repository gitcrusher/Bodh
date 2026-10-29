"""
core/serializers_byok.py

Serializers for BYOK credentials and quota status.
Ensures plaintext API keys are never returned in responses.
"""

from rest_framework import serializers

from core.models import LLMCredential


class LLMCredentialSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=True, trim_whitespace=True)
    masked_key = serializers.CharField(read_only=True)

    class Meta:
        model = LLMCredential
        fields = [
            "id",
            "provider",
            "api_key",
            "masked_key",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "masked_key", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> LLMCredential:
        api_key = validated_data.pop("api_key")
        user = validated_data.get("user")
        provider = validated_data.get("provider")

        # Update existing or create new
        credential, created = LLMCredential.objects.get_or_create(
            user=user,
            provider=provider,
            defaults=validated_data,
        )
        credential.set_api_key(api_key)
        if "is_default" in validated_data:
            credential.is_default = validated_data["is_default"]
        credential.save()

        if credential.is_default:
            LLMCredential.objects.filter(user=user).exclude(id=credential.id).update(is_default=False)

        return credential


class QuotaStatusSerializer(serializers.Serializer):
    has_byok = serializers.BooleanField()
    used = serializers.IntegerField()
    limit = serializers.IntegerField()
    remaining = serializers.IntegerField()
    is_capped = serializers.BooleanField()

