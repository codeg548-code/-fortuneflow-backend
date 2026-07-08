from django.conf import settings
from django.db import models
from rest_framework import mixins, routers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .api_services import (
    buy_pack,
    create_depot,
    create_retrait,
    get_buy_pack_preview,
    get_dashboard_data,
    get_enriched_packs,
    get_mes_packs,
    get_parrainage_summary,
)
from .models import (
    Achat,
    Client,
    Depot,
    Pack,
    Parrainage,
    ReferralInfo,
    Retrait,
    WithdrawalSuspension,
)
from .permissions import IsAuthenticatedClient
from .serializers import (
    AchatSerializer,
    ClientSerializer,
    DepotSerializer,
    PackSerializer,
    ParrainageSerializer,
    ReferralInfoSerializer,
    RetraitSerializer,
    WithdrawalSuspensionSerializer,
)


def _frontend_origin(request):
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173")


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Client.objects.all().order_by("-date_creation")
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Client.objects.all()
        return Client.objects.filter(pk=self.request.user.pk)

    @action(detail=False, methods=["get"])
    def me(self, request):
        client = Client.objects.get(pk=request.user.pk)
        return Response(ClientSerializer(client).data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        client = Client.objects.get(pk=request.user.pk)
        return Response(get_dashboard_data(client, _frontend_origin(request)))

    @action(detail=True, methods=["post"])
    def check_withdrawal_status(self, request, pk=None):
        client = self.get_object()
        can_withdraw, message = client.can_withdraw()
        return Response(
            {
                "can_withdraw": can_withdraw,
                "message": message,
                "withdrawal_suspended": client.withdrawal_suspended,
            }
        )

    @action(detail=True, methods=["post"])
    def check_referral_status(self, request, pk=None):
        client = self.get_object()
        can_refer, message = client.can_refer()
        return Response({"can_refer": can_refer, "message": message})


class PackViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pack.objects.all().order_by("montant")
    serializer_class = PackSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def enriched(self, request):
        client = (
            request.user
            if getattr(request.user, "is_authenticated", False)
            and hasattr(request.user, "codeClt")
            else None
        )
        return Response(get_enriched_packs(client))

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticatedClient])
    def buy_preview(self, request, pk=None):
        pack = self.get_object()
        client = Client.objects.get(pk=request.user.pk)
        return Response(get_buy_pack_preview(client, pack))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticatedClient])
    def buy(self, request, pk=None):
        pack = self.get_object()
        client = Client.objects.get(pk=request.user.pk)
        try:
            achat = buy_pack(client, pack)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "message": f"Félicitations ! Vous avez acheté le pack {pack.nomPack} pour {pack.montant} F.",
                "achat": AchatSerializer(achat).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AchatViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achat.objects.all()
    serializer_class = AchatSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Achat.objects.all()
        return Achat.objects.filter(codeClt=self.request.user)

    @action(detail=False, methods=["get"])
    def mes_packs(self, request):
        client = Client.objects.get(pk=request.user.pk)
        return Response(get_mes_packs(client))

    @action(detail=True, methods=["post"])
    def versement_profit(self, request, pk=None):
        achat = self.get_object()
        if achat.codeClt.pk != request.user.pk and not request.user.is_admin:
            return Response(
                {"error": "Vous ne pouvez accéder qu'à vos propres achats."},
                status=status.HTTP_403_FORBIDDEN,
            )

        success = achat.verser_profit()
        if success:
            return Response(
                {
                    "message": f"Profit de {achat.montant_total_profit} F versé avec succès.",
                    "total_amount": achat.codePack.montant + achat.montant_total_profit,
                }
            )
        return Response(
            {"error": "Le pack n'a pas encore expiré ou le profit a déjà été versé."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class DepotViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Depot.objects.all().order_by("-date_creation")
    serializer_class = DepotSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Depot.objects.all()
        return Depot.objects.filter(codeClt=self.request.user)
    
    @action(detail=False, methods=["get"], url_path="configurations-actives")
    def configurations_actives(self, request):
        from .models import ConfigurationPaiement
        configs = ConfigurationPaiement.objects.filter(est_actif=True)
        data = {}
        for c in configs:
            data[c.reseau] = {
                "label": c.get_reseau_display(),
                "numero": c.numero_reception,
                "nom": c.nom_compte,
                "syntaxe": c.syntaxe_ussd or "Via l'application officielle",
            }
        return Response(data, status=status.HTTP_200_OK)
    
    
    def create(self, request, *args, **kwargs):
        client = Client.objects.get(pk=request.user.pk)
        montant = request.data.get("montant") or request.data.get("montant_str")
        idtransaction = request.data.get("idtransaction") or request.data.get("idTransaction")
        moyen_paiement = request.data.get("moyen_paiement") or request.data.get("moyenPaiement") 
        try:
            depot = create_depot(client, montant, idtransaction, moyen_paiement)
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
        return Response(
            DepotSerializer(depot).data,
            status=status.HTTP_201_CREATED,
        )
    
    


class RetraitViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Retrait.objects.all().order_by("-date_creation")
    serializer_class = RetraitSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Retrait.objects.all()
        return Retrait.objects.filter(codeClt=self.request.user)

    def create(self, request, *args, **kwargs):
        client = Client.objects.get(pk=request.user.pk)
        montant = request.data.get("montant")
        try:
            retrait, frais, montant_net = create_retrait(client, montant)
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
        return Response(
            {
                "retrait": RetraitSerializer(retrait).data,
                "frais": frais,
                "montant_net": montant_net,
                "message": (
                    f"Demande de retrait de {montant_net} F soumise "
                    f"(Frais : {frais} F). En attente de validation."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ParrainageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Parrainage.objects.all().order_by("-date_creation")
    serializer_class = ParrainageSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Parrainage.objects.all()
        return Parrainage.objects.filter(
            models.Q(parrain=self.request.user) | models.Q(filleul=self.request.user)
        )

    @action(detail=False, methods=["get"])
    def mes_filleuls(self, request):
        parrainages = Parrainage.objects.filter(parrain=request.user)
        serializer = self.get_serializer(parrainages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        client = Client.objects.get(pk=request.user.pk)
        return Response(get_parrainage_summary(client, _frontend_origin(request)))


class WithdrawalSuspensionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WithdrawalSuspension.objects.all()
    serializer_class = WithdrawalSuspensionSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return WithdrawalSuspension.objects.all()
        return WithdrawalSuspension.objects.filter(client=self.request.user)


class ReferralInfoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReferralInfo.objects.all()
    serializer_class = ReferralInfoSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return ReferralInfo.objects.all()
        return ReferralInfo.objects.filter(
            models.Q(sponsor=self.request.user) | models.Q(sponsored_client=self.request.user)
        )

    @action(detail=False, methods=["get"])
    def mes_filleuls_referral(self, request):
        referrals = ReferralInfo.objects.filter(sponsor=request.user)
        serializer = self.get_serializer(referrals, many=True)
        return Response(serializer.data)


api_router = routers.DefaultRouter()
api_router.register(r"clients", ClientViewSet, basename="client")
api_router.register(r"packs", PackViewSet, basename="pack")
api_router.register(r"achats", AchatViewSet, basename="achat")
api_router.register(r"depots", DepotViewSet, basename="depot")
api_router.register(r"retraits", RetraitViewSet, basename="retrait")
api_router.register(r"parrainages", ParrainageViewSet, basename="parrainage")
api_router.register(r"withdrawals-suspension", WithdrawalSuspensionViewSet, basename="withdrawal-suspension")
api_router.register(r"referral-info", ReferralInfoViewSet, basename="referral-info")
