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
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        data = get_dashboard_data(request.user, _frontend_origin(request))
        return Response(data)


class PackViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pack.objects.all().order_by("montant")
    serializer_class = PackSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        return Pack.objects.all().order_by("montant")

    def list(self, request, *args, **kwargs):
        data = get_enriched_packs(request.user)
        return Response(data)


class AchatViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Achat.objects.all().order_by("-date_achat")
    serializer_class = AchatSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Achat.objects.all()
        return Achat.objects.filter(codeClt=self.request.user)

    @action(detail=False, methods=["get"])
    def mes_packs(self, request):
        data = get_mes_packs(request.user)
        return Response(data)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        pack = Pack.objects.get(pk=pk)
        data = get_buy_pack_preview(request.user, pack)
        return Response(data)

    def create(self, request, *args, **kwargs):
        pack_id = request.data.get("pack_id") or request.data.get("codePack")
        if not pack_id:
            raise ValidationError({"detail": "Le pack_id est obligatoire."})
        try:
            pack = Pack.objects.get(pk=pack_id)
            achat = buy_pack(request.user, pack)
        except Pack.DoesNotExist:
            raise ValidationError({"detail": "Pack introuvable."})
        except ValueError as e:
            raise ValidationError({"detail": str(e)})

        return Response(AchatSerializer(achat).data, status=status.HTTP_201_CREATED)


class DepotViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Depot.objects.all().order_by("-date_creation")
    serializer_class = DepotSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Depot.objects.all()
        return Depot.objects.filter(codeClt=self.request.user)

    # === L'ACTION A BIEN ÉTÉ PLACÉE ICI DANS LA CLASSE ===
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
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
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
            retrait = create_retrait(client, montant)
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
        return Response(
            RetraitSerializer(retrait).data,
            status=status.HTTP_201_CREATED,
        )


class ParrainageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Parrainage.objects.all().order_by("-date_creation")
    serializer_class = ParrainageSerializer
    permission_classes = [IsAuthenticatedClient]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Parrainage.objects.all()
        return Parrainage.objects.filter(parrain=self.request.user)

    def list(self, request, *args, **kwargs):
        data = get_parrainage_summary(request.user, _frontend_origin(request))
        return Response(data)


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
api_router.register(r"withdrawals-suspension", WithdrawalSuspensionViewSet, basename="withdrawal")