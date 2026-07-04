import random

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Client, Parrainage
from .permissions import IsAuthenticatedClient
from .serializers import ClientSerializer
from .tokens import ClientToken


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        numero = request.data.get("numero", "").strip()
        mdp = request.data.get("mdp", "")

        if not numero or not mdp:
            return Response(
                {"detail": "Veuillez remplir tous les champs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=numero, password=mdp)
        if user is None:
            return Response(
                {"detail": "Mot de passe ou Numéro incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = ClientToken.get_or_create_for_client(user)
        return Response(
            {
                "token": token.key,
                "user": ClientSerializer(user).data,
            }
        )


class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, ref=None):
        nom_complet = request.data.get("nom", "").strip()
        numerotel = request.data.get("numero", "").strip()
        pwd = request.data.get("mdp", "")
        cmdp = request.data.get("cmdp", "")

        if pwd != cmdp:
            return Response(
                {"detail": "Les mots de passe ne correspondent pas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parrain_id = 0
        parrain_instance = None

        ref_value = ref or request.data.get("ref") or request.data.get("parrain")
        if ref_value is not None and str(ref_value).isdigit():
            try:
                parrain_instance = Client.objects.get(codeClt=int(ref_value))
                parrain_id = parrain_instance.codeClt
            except Client.DoesNotExist:
                pass

        try:
            with transaction.atomic():
                code_client = random.randint(1000000, 9999999)
                hashedpwd = make_password(pwd)
                moyen_paiement = request.data.get("moyen_paiement", "MTN").strip()
                nom_beneficiaire = request.data.get("nom_beneficiaire", "").strip() or None
                numero_portefeuille = request.data.get("numero_portefeuille", "").strip() or None

                nouveau_client = Client.objects.create(
                    codeClt=code_client,
                    nomClt=nom_complet,
                    numero=numerotel,
                    mdp=hashedpwd,
                    moyen_paiement=moyen_paiement,
                    nom_beneficiaire=nom_beneficiaire,
                    numero_portefeuille=numero_portefeuille,
                    codeParrain=parrain_id,
                )

                if parrain_instance:
                    Parrainage.objects.create(
                        parrain=parrain_instance,
                        filleul=nouveau_client,
                        commission_versee=False,
                    )

                token = ClientToken.get_or_create_for_client(nouveau_client)
                return Response(
                    {
                        "token": token.key,
                        "user": ClientSerializer(nouveau_client).data,
                        "message": (
                            f"Inscription réussie! Votre parrain est : {parrain_instance.nomClt}"
                            if parrain_instance
                            else "Inscription réussie!"
                        ),
                    },
                    status=status.HTTP_201_CREATED,
                )
        except IntegrityError:
            return Response(
                {"detail": "Ce numéro de téléphone est déjà enregistré."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": f"Erreur lors de l'enregistrement: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticatedClient]

    def post(self, request):
        ClientToken.objects.filter(client=request.user).delete()
        return Response({"detail": "Déconnecté"})


class MeAPIView(APIView):
    permission_classes = [IsAuthenticatedClient]

    def get(self, request):
        client = Client.objects.get(pk=request.user.pk)
        return Response(ClientSerializer(client).data)

    def patch(self, request):
        client = Client.objects.get(pk=request.user.pk)
        numero = request.data.get("numero", client.numero)
        if isinstance(numero, str):
            numero = numero.strip()
        if numero != client.numero and Client.objects.filter(numero=numero).exclude(pk=client.pk).exists():
            return Response(
                {"detail": "Ce numéro est déjà utilisé par un autre compte."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "nom" in request.data or "nomClt" in request.data:
            client.nomClt = (request.data.get("nom") or request.data.get("nomClt") or client.nomClt).strip()
        if "numero" in request.data:
            client.numero = numero
        if "moyen_paiement" in request.data:
            client.moyen_paiement = request.data["moyen_paiement"]
        if "nom_beneficiaire" in request.data:
            client.nom_beneficiaire = request.data["nom_beneficiaire"].strip() or None
        if "numero_portefeuille" in request.data:
            client.numero_portefeuille = request.data["numero_portefeuille"].strip() or None

        client.save(
            update_fields=[
                "nomClt",
                "numero",
                "moyen_paiement",
                "nom_beneficiaire",
                "numero_portefeuille",
            ]
        )
        return Response(ClientSerializer(client).data)
