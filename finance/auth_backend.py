from .models import Client
from django.contrib.auth.hashers import check_password

class ClientBackend:
    """
    Backend d'authentification personnalisé pour le modèle Client.
    Utilise le champ 'numero' comme identifiant (username) et vérifie le hachage
    du mot de passe stocké dans 'mdp'.
    """
    def authenticate(self, request, username=None, password=None):
        try:
            client = Client.objects.get(numero=username)
            if check_password(password, client.mdp):
                return client 
        except Client.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        """Recherche le client par sa clé primaire (codeClt) pour la session."""
        try:
            return Client.objects.get(pk=user_id)
        except Client.DoesNotExist:
            return None