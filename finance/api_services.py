import random
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .constants import (
    COMMISSION_RATE,
    FRAIS_POURCENTAGE_RETRAIT,
    MINIMUM_RECHARGE,
    MONTANT_MINIMUM_RETRAIT,
)
from .helpers import enrichir_packs_pour_client, pack_peut_etre_achete
from .models import Achat, Client, Depot, Pack, Parrainage, Retrait
from .serializers import PackSerializer


def get_dashboard_data(client, frontend_origin="http://localhost:5173"):
    return {
        "nom": client.nomClt,
        "numero": client.numero,
        "solde": client.solde,
        "revenu": client.revenu,
        "id": client.pk,
        "parrainage_link": f"{frontend_origin}/signup/{client.pk}",
    }


def get_enriched_packs(client=None):
    packs = Pack.objects.all().order_by("montant")
    result = []
    for item in enrichir_packs_pour_client(packs, client):
        pack_data = PackSerializer(item["pack"]).data
        pack_data.update(
            {
                "peut_acheter": item["peut_acheter"],
                "message_blocage": item["message_blocage"],
                "deja_achete": item["deja_achete"],
                "est_en_stock": item["est_en_stock"],
                "stock_disponible": item["stock_disponible"],
                "stock_initial": item["stock_initial"],
            }
        )
        result.append(pack_data)
    return result


def get_buy_pack_preview(client, pack):
    montant_pack = pack.montant
    solde_client = int(getattr(client, "solde", 0) or 0)
    peut_acheter, message_blocage = pack_peut_etre_achete(client, pack)
    if solde_client < montant_pack:
        peut_acheter = False
        message_blocage = (
            f"Solde insuffisant : {solde_client} F. Vous avez besoin de {montant_pack} F."
        )
    return {
        "pack": PackSerializer(pack).data,
        "client_solde": solde_client,
        "peut_acheter": peut_acheter,
        "message_blocage": message_blocage,
    }


def buy_pack(client, pack):
    preview = get_buy_pack_preview(client, pack)
    if not preview["peut_acheter"]:
        raise ValueError(preview["message_blocage"] or "Achat impossible.")

    montant_pack = pack.montant
    with transaction.atomic():
        client_to_update = Client.objects.select_for_update().get(pk=client.pk)
        if client_to_update.solde < montant_pack:
            raise ValueError(
                f"Solde insuffisant: {client_to_update.solde} FCFA. "
                f"Vous avez besoin de {montant_pack} FCFA."
            )

        client_to_update.solde -= montant_pack
        premier_achat = not Achat.objects.filter(codeClt=client_to_update).exists()
        client_to_update.save(update_fields=["solde"])

        achat = Achat.objects.create(
            codeClt=client_to_update,
            codePack=pack,
        )

        if client_to_update.codeParrain != 0 and premier_achat:
            try:
                lien_parrainage = Parrainage.objects.select_for_update().get(
                    filleul=client_to_update
                )
                if not lien_parrainage.commission_versee:
                    parrain = lien_parrainage.parrain
                    commission_montant = int(montant_pack * COMMISSION_RATE)
                    Client.objects.filter(pk=parrain.pk).update(
                        solde=F("solde") + commission_montant
                    )
                    lien_parrainage.commission_versee = True
                    lien_parrainage.save(update_fields=["commission_versee"])
            except Parrainage.DoesNotExist:
                pass

    return achat


def create_depot(client, montant_str, idtransaction=None):
    if not (client.numero_portefeuille and client.nom_beneficiaire):
        raise ValueError(
            "Veuillez renseigner votre moyen de paiement dans la page Mon compte avant de recharger."
        )

    try:
        montant = Decimal(str(montant_str).strip())
        if montant <= 0:
            raise ValueError("Le montant doit être supérieur à zéro.")
    except (InvalidOperation, TypeError):
        raise ValueError("Le montant saisi n'est pas un nombre valide.")

    if montant < MINIMUM_RECHARGE:
        raise ValueError(f"Le montant minimum de recharge est de {MINIMUM_RECHARGE} FCFA.")

    if not idtransaction:
        idtransaction = f"DEP{random.randint(100000, 999999)}"

    if Depot.objects.filter(idTransaction=idtransaction).exists():
        raise ValueError(
            "Cet ID de transaction est déjà enregistré. Veuillez vérifier ou contacter le support."
        )

    nom = client.nom_beneficiaire or client.nomClt
    numero = client.numero_portefeuille

    return Depot.objects.create(
        codeClt=client,
        nomNum=nom,
        numDepot=numero,
        montant=int(montant),
        idTransaction=idtransaction,
        statut="en attente",
    )


def create_retrait(client, montant_str):
    if not (client.numero_portefeuille and client.nom_beneficiaire):
        raise ValueError(
            "Veuillez renseigner votre moyen de paiement dans la page Mon compte avant de retirer."
        )

    can_withdraw, withdrawal_message = client.can_withdraw()
    if not can_withdraw:
        raise ValueError(withdrawal_message)

    try:
        montant_retrait = int(montant_str)
    except (ValueError, TypeError):
        raise ValueError("Le montant du retrait doit être un nombre entier valide.")

    if montant_retrait < MONTANT_MINIMUM_RETRAIT:
        raise ValueError(f"Le montant minimum de retrait est de {MONTANT_MINIMUM_RETRAIT} F.")

    if montant_retrait % 100 != 0:
        raise ValueError("Le montant doit être un multiple de 100 FCFA.")

    if montant_retrait > client.solde:
        raise ValueError(f"Solde insuffisant. Votre solde est de {client.solde} FCFA.")

    frais = int(montant_retrait * FRAIS_POURCENTAGE_RETRAIT)
    montant_deduire_solde = montant_retrait
    montant_net_retire = montant_retrait - frais
    payment_name = client.nom_beneficiaire or client.nomClt
    payment_number = client.numero_portefeuille

    with transaction.atomic():
        client_to_update = Client.objects.select_for_update().get(pk=client.pk)
        if client_to_update.solde < montant_deduire_solde:
            raise ValueError(
                f"Solde insuffisant. Votre solde est de {client_to_update.solde} FCFA."
            )

        Client.objects.filter(pk=client_to_update.pk).update(
            solde=F("solde") - montant_deduire_solde
        )

        retrait = Retrait.objects.create(
            codeClt=client_to_update,
            nomNum=payment_name,
            numRetrait=payment_number,
            montant=montant_net_retire,
            statut="en attente",
        )

    return retrait, frais, montant_net_retire


def get_mes_packs(client):
    maintenant = timezone.now()
    packs_achats = (
        Achat.objects.filter(codeClt_id=client.pk)
        .select_related("codePack")
        .order_by("-date_creation")
    )

    details = []
    for achat in packs_achats:
        pack_base = achat.codePack
        if achat.date_expiration is not None:
            temps_avant_expiration = achat.date_expiration - maintenant
            if achat.is_expired():
                if achat.profit_versé:
                    statut = "Expiré - Profit versé"
                    temps_affichage = "Profit crédité"
                else:
                    statut = "Expiré - En attente de versement"
                    temps_affichage = "Versement en cours de traitement"
            else:
                total_secondes = max(0, temps_avant_expiration.total_seconds())
                jours = int(total_secondes // 86400)
                heures = int((total_secondes % 86400) // 3600)
                minutes = int((total_secondes % 3600) // 60)
                statut = "Actif"
                temps_affichage = f"Expiration dans : {jours}j {heures}h {minutes}m"
        else:
            statut = "Actif"
            temps_affichage = "Expiration non définie"

        details.append(
            {
                "codeAchat": achat.codeAchat,
                "date_achat": achat.date_creation,
                "nom_pack": pack_base.nomPack,
                "montant_investi": pack_base.montant,
                "montant_total_profit": achat.montant_total_profit,
                "profit_versé": achat.profit_versé,
                "date_expiration": achat.date_expiration,
                "statut": statut,
                "temps_affichage": temps_affichage,
                "is_active": achat.is_active,
            }
        )
    return details


def get_parrainage_summary(client, frontend_origin="http://localhost:5173"):
    liens = (
        Parrainage.objects.filter(parrain=client)
        .select_related("filleul")
        .order_by("-date_creation")
    )

    filleuls_data = []
    total_invested_all = 0
    for lien in liens:
        filleul = lien.filleul
        achats = Achat.objects.filter(codeClt=filleul).select_related("codePack")
        invested = achats.aggregate(total=Sum("codePack__montant"))["total"] or 0
        total_profit = (
            achats.aggregate(total_profit=Sum("montant_total_profit"))["total_profit"] or 0
        )
        packs = (
            ", ".join(list(achats.values_list("codePack__nomPack", flat=True).distinct()))
            or "—"
        )
        filleuls_data.append(
            {
                "nom": filleul.nomClt or f"Client #{filleul.codeClt}",
                "numero": filleul.numero,
                "invested": invested,
                "reported": total_profit,
                "packs": packs,
                "commission_versée": lien.commission_versee,
                "date_creation": lien.date_creation,
            }
        )
        total_invested_all += invested

    return {
        "filleuls": filleuls_data,
        "parrainage_link": f"{frontend_origin}/signup/{client.pk}",
        "parrainage_count": len(filleuls_data),
        "total_invested_all": total_invested_all,
    }
