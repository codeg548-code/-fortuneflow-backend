import secrets

from django.db import models
from django.utils import timezone

from .models import Client


def generate_token_key():
    return secrets.token_hex(20)


class ClientToken(models.Model):
    """Token d'authentification API pour le modèle Client."""

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    key = models.CharField(max_length=40, unique=True, default=generate_token_key)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Token API Client"

    def __str__(self):
        return f"Token {self.client.codeClt}"

    @classmethod
    def get_or_create_for_client(cls, client):
        token, _ = cls.objects.get_or_create(client=client)
        return token
