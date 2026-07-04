from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .tokens import ClientToken


class ClientTokenAuthentication(BaseAuthentication):
    """Authentification par en-tête : Authorization: Token <key>"""

    keyword = "Token"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        key = auth_header[len(self.keyword) + 1 :].strip()
        if not key:
            return None

        try:
            token = ClientToken.objects.select_related("client").get(key=key)
        except ClientToken.DoesNotExist:
            raise AuthenticationFailed("Token invalide.")

        if not token.client.is_active:
            raise AuthenticationFailed("Compte désactivé.")

        return (token.client, token)
