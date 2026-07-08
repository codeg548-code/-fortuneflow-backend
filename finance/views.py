from .helpers import enrichir_packs_pour_client, pack_peut_etre_achete
from .models import Client, Pack, Achat, Depot, Retrait, Parrainage, WithdrawalSuspension
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction, connection
from django.db.models import F, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from django.conf import settings
import logging
import random

logger = logging.getLogger(__name__)

COMMISSION_RATE = 0.05
MONTANT_MINIMUM_RETRAIT = 1000
MINIMUM_RECHARGE = 2500
FRAIS_POURCENTAGE_RETRAIT = 0.10


def api_ping(request):
    """
    Route publique pour maintenir Render et Aiven éveillés.
    Exécute une requête SQL minimale.
    """
    try:
        # Un simple 'SELECT 1' force la connexion à Aiven sans charger de données
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "connected"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def _is_payment_configured(client):
    return bool(
        getattr(client, "moyen_paiement", None)
        and getattr(client, "numero_portefeuille", None)
        and getattr(client, "nom_beneficiaire", None)
    )


def _get_payment_rows(client):
    return [
        {
            "label": "Moyen de paiement",
            "value": client.get_moyen_paiement_display()
            if hasattr(client, "get_moyen_paiement_display")
            else client.moyen_paiement,
        },
        {"label": "Nom du bénéficiaire", "value": client.nom_beneficiaire or "—"},
        {"label": "Numéro de portefeuille", "value": client.numero_portefeuille or "—"},
    ]


def is_superuser(user):
    return user.is_superuser


def signup_view(request, ref=None):
    """
    Gère l'enregistrement du Client.
    Gère l'attribution du parrain via l'URL (?ref=) ou le formulaire.
    """
    # Utilisation d'une transaction atomique pour garantir la création du Client ET du Parrainage.
    with transaction.atomic():
        codeClient = random.randint(1000000, 9999999)

        if request.method == "POST":
            # ... (récupération des données du formulaire) ...
            nom_complet = request.POST.get("nom", "").strip()
            numerotel = request.POST.get("numero", "").strip()
            pwd = request.POST.get("mdp", "")
            cmdp = request.POST.get("cmdp", "")

            # Logique pour déterminer l'ID du parrain
            parrain_id = 0 # Utilisé pour le champ codeParrain
            parrain_instance = None # Utilisé pour la FK dans Parrainage

            # Si 'ref' est passé dans l'URL ou si un code est dans le formulaire
            # (Note: Votre logique actuelle utilise uniquement ref/URL, je m'y tiens)
            if ref is not None:

            # Utiliser ref_str pour la validation
                if str(ref).isdigit():
                    # Tente de trouver le parrain dans la base
                    try:
                        parrain_instance = Client.objects.get(codeClt=int(ref))
                        parrain_id = parrain_instance.codeClt
                    except Client.DoesNotExist:
                        messages.warning(request, "Le code parrain n'est pas valide.")
                        # Parrain_id reste 0

            # Si un champ parrain est dans le formulaire (à ajouter si nécessaire)
            # elif request.POST.get("code_parrain"):
            #     ...

            if pwd != cmdp:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                return render(request, "finance/signup_view.html")

            try:
                hashedpwd = make_password(pwd)

                # 1. Création du Client
                moyen_paiement = request.POST.get("moyen_paiement", "MTN").strip()
                nom_beneficiaire = request.POST.get("nom_beneficiaire", "").strip() or None
                numero_portefeuille = request.POST.get("numero_portefeuille", "").strip() or None

                nouveau_client = Client.objects.create(
                    codeClt=codeClient,
                    nomClt=nom_complet,
                    numero=numerotel,
                    mdp=hashedpwd,
                    moyen_paiement=moyen_paiement,
                    nom_beneficiaire=nom_beneficiaire,
                    numero_portefeuille=numero_portefeuille,
                    # Stocke l'ID du parrain dans le champ historique codeParrain
                    codeParrain=parrain_id,
                )

                # 2. Création de l'entrée Parrainage
                if parrain_instance:
                    Parrainage.objects.create(
                        parrain=parrain_instance, # L'objet Client du parrain
                        filleul=nouveau_client,   # L'objet Client du nouveau client
                        commission_versee=False   # Statut initial
                    )
                    messages.success(request, f"Inscription réussie! Votre parrain est : {parrain_instance.nomClt}")
                else:
                    messages.success(request, "Inscription réussie! (Sans parrain)")

                return render(request, "finance/login_view.html")

            except IntegrityError:
                # Gérer l'erreur si le numero est déjà utilisé
                messages.error(request, "Ce numéro de téléphone est déjà enregistré.")
                return render(request, "finance/signup_view.html")
            except Exception as e:
                # Gérer autres erreurs
                messages.error(request, f"Erreur lors de l'enregistrement: {e}")
                return render(request, "finance/signup_view.html")

        # ... (Logique GET) ...
        return render(request, "finance/signup_view.html", {"ref": ref})

def login_view(request):
    # if request.user.is_authenticated:
    #     return redirect("accueil")

    if request.method == "POST":
        numero = request.POST.get("numero", "")
        mdp = request.POST.get("mdp", "")

        if not numero or not mdp:
            messages.error(request, "Veuillez remplir tous les champs")
            return render(request, "finance/login_view.html")
        user = authenticate(request, username=numero, password=mdp)

        if user is not None:
            login(request, user)
            if hasattr(user, "is_validator") and user.is_validator:
                return redirect("validate_depot_list")
            else:
                return redirect("accueil")
        else:
            messages.error(request, "Mot de passe ou Numéro incorrect")
            return render(request, "finance/login_view.html")

    return render(request, "finance/login_view.html")

# Déconnecte l'utilisateur et redirige vers la page de connexion.
def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté(e).")
    return redirect("login")


# Récupère les données du client connecté en rechargeant l'instance depuis la BD
# pour garantir que le solde et le revenu sont à jour.
@login_required(login_url="login")
def accueil_view(request):

    try:
        user = Client.objects.get(pk=request.user.pk)
    except Client.DoesNotExist:
        messages.error(request, "Profil introuvable. Veuillez vous reconnecter.")
        return redirect("logout")

    nom_utilisateur = getattr(user, "nomClt", "Client Inconnu")

    context = {
        "nom": nom_utilisateur,
        "numero": getattr(user, "numero", "N/A"),
        "solde": getattr(user, "solde", 0),
        "revenu": getattr(user, "revenu", 0),
        "id": user.pk,
        "HOST": f"http://{request.get_host()}/signup?ref={user.pk}",
    }

    return render(request, "finance/accueil_view.html", context)


@login_required(login_url="login")
def compte_view(request):
    client = get_object_or_404(Client, pk=request.user.pk)

    if request.method == "POST":
        numero = request.POST.get("numero", client.numero).strip()
        if numero != client.numero and Client.objects.filter(numero=numero).exclude(pk=client.pk).exists():
            messages.error(request, "Ce numéro est déjà utilisé par un autre compte.")
            return redirect("compte")

        client.nomClt = request.POST.get("nom", client.nomClt).strip() or client.nomClt
        client.numero = numero
        client.moyen_paiement = request.POST.get("moyen_paiement", client.moyen_paiement)
        client.nom_beneficiaire = request.POST.get("nom_beneficiaire", client.nom_beneficiaire).strip() or None
        client.numero_portefeuille = request.POST.get("numero_portefeuille", client.numero_portefeuille).strip() or None
        client.save(update_fields=["nomClt", "numero", "moyen_paiement", "nom_beneficiaire", "numero_portefeuille"])

        messages.success(request, "Vos informations de compte ont été mises à jour.")
        return redirect("compte")

    parrainage_actif = Parrainage.objects.filter(parrain=client).select_related("filleul")

    payment_rows = _get_payment_rows(client)
    payment_complete = _is_payment_configured(client)

    context = {
        "client": client,
        "parrainage_count": parrainage_actif.count(),
        "parrainage_link": f"http://{request.get_host()}/signup?ref={client.pk}",
        "payment_rows": payment_rows,
        "payment_complete": payment_complete,
        "numero_display": client.numero,
        "solde_display": getattr(client, 'solde', 0),
        "revenu_display": getattr(client, 'revenu', 0),
    }
    return render(request, "finance/compte_view.html", context)


@login_required(login_url="login")
def parrainage_view(request):
    client = get_object_or_404(Client, pk=request.user.pk)
    liens = (
        Parrainage.objects.filter(parrain=client)
        .select_related("filleul")
        .order_by("-date_creation")
    )

    # Construire des données enrichies pour chaque filleul
    filleuls_data = []
    total_invested_all = 0
    for lien in liens:
        filleul = lien.filleul
        achats = Achat.objects.filter(codeClt=filleul).select_related('codePack')
        invested = achats.aggregate(total=Sum('codePack__montant'))['total'] or 0
        total_profit = achats.aggregate(total_profit=Sum('montant_total_profit'))['total_profit'] or 0
        packs = ", ".join(list(achats.values_list('codePack__nomPack', flat=True).distinct())) or '—'
        filleuls_data.append({
            'nom': filleul.nomClt or f'Client #{filleul.codeClt}',
            'numero': filleul.numero,
            'invested': invested,
            'reported': total_profit,
            'packs': packs,
            'commission_verssee': lien.commission_versee,
            'date_creation': lien.date_creation,
        })
        total_invested_all += invested

    context = {
        "client": client,
        "filleuls": filleuls_data,
        "parrainage_link": f"http://{request.get_host()}/signup?ref={client.pk}",
        "parrainage_count": len(filleuls_data),
        "total_invested_all": total_invested_all,
    }
    return render(request, "finance/parrainage_view.html", context)


#ENREGISTREMENT D'UN DEPOT
@login_required
def depot_view(request):
    client_data = get_object_or_404(Client, pk=request.user.pk)
    payment_rows = _get_payment_rows(client_data)
    carte_configuree = _is_payment_configured(client_data)
    context = {
        "payment_rows": payment_rows,
        "carte_configuree": carte_configuree,
        "MINIMUM_RECHARGE": MINIMUM_RECHARGE,
    }

    if request.method == "POST":
        if not carte_configuree:
            messages.error(
                request,
                "Veuillez renseigner votre moyen de paiement dans la page Mon compte avant de recharger.",
            )
            return redirect("compte")

        montant_str = request.POST.get("montant_str", "").strip()
        idtransaction = request.POST.get("idtransaction", "").strip() or None

        try:
            montant = Decimal(montant_str)
            if montant <= 0:
                messages.error(request, "Le montant doit être supérieur à zéro.")
                return render(request, "finance/depot_view.html", context)
        except InvalidOperation:
            messages.error(request, "Le montant saisi n'est pas un nombre valide.")
            return render(request, "finance/depot_view.html", context)

        if montant < MINIMUM_RECHARGE:
            messages.error(
                request,
                f"Le montant minimum de recharge est de {MINIMUM_RECHARGE} FCFA.",
            )
            return render(request, "finance/depot_view.html", context)

        if not idtransaction:
            idtransaction = f"DEP{random.randint(100000, 999999)}"

        if Depot.objects.filter(idTransaction=idtransaction).exists():
            messages.error(
                request,
                "Cet ID de transaction est déjà enregistré. Veuillez vérifier ou contacter le support.",
            )
            return render(request, "finance/depot_view.html", context)

        try:
            nom = client_data.nom_beneficiaire or client_data.nomClt
            numero = client_data.numero_portefeuille

            Depot.objects.create(
                codeClt_id=request.user.pk,
                nomNum=nom,
                numDepot=numero,
                montant=montant,
                idTransaction=idtransaction,
                statut="en attente",
            )
            messages.success(
                request, "Votre dépôt a été soumis pour validation avec succès."
            )
            return redirect("accueil")

        except Exception as e:
            print(f"Erreur Depot: {e}")
            messages.error(request, e)
            return render(request, "finance/depot_view.html", context)

    return render(request, "finance/depot_view.html", context)


# FONCTION POUR EFFECTUER UN RETRAIT

@login_required(login_url="login")
def retrait_view(request):
    try:
        client_data = Client.objects.get(pk=request.user.pk)
        solde_actuel = client_data.solde
    except Client.DoesNotExist:
        messages.error(request, "Impossible de récupérer votre profil client.")
        return redirect("accueil")

    # Vérifier si l'utilisateur peut faire un retrait
    can_withdraw, withdrawal_message = client_data.can_withdraw()
    if not can_withdraw:
        messages.error(request, withdrawal_message)
        return redirect("accueil")

    payment_rows = _get_payment_rows(client_data)
    carte_configuree = _is_payment_configured(client_data)

    if request.method == "POST":
        try:
            montant_retrait_form = int(request.POST.get("montant"))
            nom_compte = request.POST.get("nom", "").strip() or None

            numero_compte_str = request.POST.get("numero", "").strip()
            numero_compte = (
                int(numero_compte_str)
                if numero_compte_str and numero_compte_str.isdigit()
                else None
            )

        except (ValueError, TypeError):
            messages.error(
                request, "Le montant du retrait doit être un nombre entier valide."
            )
            return redirect("retrait")
        
        if montant_retrait_form < MONTANT_MINIMUM_RETRAIT:
            messages.error(
                request,
                f"Le montant minimum de retrait est de {MONTANT_MINIMUM_RETRAIT} F.",
            )
            return redirect("retrait")

        if montant_retrait_form % 100 != 0:
            messages.error(
                request,
                "Le montant doit être un multiple de 100 FCFA.",
            )
            return redirect("retrait")

        if montant_retrait_form > solde_actuel:
            messages.error(
                request, f"Solde insuffisant. Votre solde est de {solde_actuel} FCFA."
            )
            return redirect("retrait")
        
        frais = int(montant_retrait_form * FRAIS_POURCENTAGE_RETRAIT)
        montant_deduire_solde = montant_retrait_form
        montant_net_retire = montant_retrait_form - frais

        if not carte_configuree:
            messages.error(
                request,
                "Veuillez renseigner votre moyen de paiement dans la page Mon compte avant de retirer.",
            )
            return redirect("compte")

        try:
            payment_name = client_data.nom_beneficiaire or client_data.nomClt
            payment_number = client_data.numero_portefeuille

            with transaction.atomic():
                client_to_update = Client.objects.select_for_update().get(pk=request.user.pk)

                if client_to_update.solde < montant_deduire_solde:
                    messages.error(
                        request,
                        f"Solde insuffisant. Votre solde est de {client_to_update.solde} FCFA.",
                    )
                    return redirect("retrait")

                Client.objects.filter(pk=client_to_update.pk).update(
                    solde=F("solde") - montant_deduire_solde
                )
                client_to_update.refresh_from_db(fields=["solde"])

                Retrait.objects.create(
                    codeClt=client_to_update,
                    nomNum=payment_name,
                    numRetrait=payment_number,
                    montant=montant_net_retire,
                    statut="en attente",
                )

            messages.success(
                request,
                f"Demande de retrait de **{montant_net_retire} F** soumise (Frais : {frais} F). En attente de validation.",
            )
            return redirect("mes-retraits")

        except ValueError as e:
            logger.warning("Validation de retrait échouée : %s", e)
            messages.error(request, str(e))
            return redirect("retrait")
        except Exception as e:
            logger.exception("Erreur critique d'enregistrement de retrait")
            messages.error(
                request,
                "Une erreur s'est produite lors de l'enregistrement de la transaction. Votre solde n'a pas été débité. Veuillez réessayer.",
            )
            return redirect("retrait")

    context = {
        "solde_compte": solde_actuel,
        "MONTANT_MINIMUM_RETRAIT": MONTANT_MINIMUM_RETRAIT,
        "carte_configuree": carte_configuree,
        "payment_rows": payment_rows,
    }
    return render(request, "finance/retrait_view.html", context)


# FONCTION POUR VOIR LA LISTE DES PACKS DISPONIBLES

def pack_view(request):
    try:
        tous_les_packs = Pack.objects.all().order_by("montant")
    except Exception as e:
        print(f"Erreur lors de la récupération des packs: {e}")
        tous_les_packs = []

    client = request.user if getattr(request.user, "is_authenticated", False) else None
    client_data = client if isinstance(client, Client) else None
    packs_detail = enrichir_packs_pour_client(tous_les_packs, client_data)

    context = {"packs_detail": packs_detail}
    return render(request, "finance/pack_view.html", context)


# CODE D'ACHAT DE PACK
# ET VERSEMENT DE COMISSION D'UN PARRAIN

@login_required(login_url="login")
def buypack_view(request, pack_id):
    try:
        pack_to_buy = get_object_or_404(Pack, pk=pack_id)
        montant_pack = pack_to_buy.montant
    except Pack.DoesNotExist:
        messages.error(request, "Erreur: Le pack demandé n'existe pas.")
        return redirect("packs")

    # On charge l'objet client initialement pour les vérifications et le contexte.
    try:
        # Utilisez 'request.user' directement puisque c'est un objet Client
        client_data = Client.objects.get(pk=request.user.pk)
    except Client.DoesNotExist:
        messages.error(request, "Erreur: Profil client introuvable.")
        return redirect("packs")

    solde_client = int(getattr(client_data, "solde", 0) or 0)
    peut_acheter, message_blocage = pack_peut_etre_achete(client_data, pack_to_buy)
    if solde_client < montant_pack:
        peut_acheter, message_blocage = False, f"Solde insuffisant : {solde_client} F. Vous avez besoin de {montant_pack} F."

    context = {
        "getpack": pack_to_buy,
        "client": client_data,
        "montant_pack": montant_pack,
        "peut_acheter": peut_acheter,
        "message_blocage": message_blocage,
    }

    if request.method == "POST" and "valider" in request.POST:
        try:
            # Démarrer la transaction atomique pour garantir l'intégrité des données
            with transaction.atomic():

                # IMPORTANT: Rechargez et verrouillez l'objet client À L'INTÉRIEUR de la transaction
                # Ceci garantit que la vérification du solde est faite sur les données les plus récentes
                client_to_update = Client.objects.select_for_update().get(pk=request.user.pk)

                if client_to_update.solde < montant_pack:
                    messages.error(
                        request,
                        f"Solde insuffisant: {client_to_update.solde} FCFA. Vous avez besoin de {montant_pack} FCFA.",
                    )
                    return render(request, "finance/buypack_view.html", context)

                else:
                    # 1. Déduction du solde du client
                    client_to_update.solde -= montant_pack
                    
                    # Vérification si c'est le PREMIER achat de pack du client (filleul)
                    premier_achat = not Achat.objects.filter(codeClt=client_to_update).exists()
                    
                    client_to_update.save(update_fields=["solde"])

                    # 2. Création de l'Achat avec nouveau modèle
                    achat = Achat.objects.create(
                        codeClt=client_to_update,
                        codePack=pack_to_buy,
                    )

                    # --- LOGIQUE DE COMMISSION PARRAINAGE ---
                    # Vérifier si le client a un parrain ET si c'est son premier achat
                    if client_to_update.codeParrain != 0 and premier_achat:
                        try:
                            # 3. Récupérer le lien de Parrainage pour ce Filleul (verrouillage)
                            lien_parrainage = Parrainage.objects.select_for_update().get(filleul=client_to_update)

                            # 4. Vérifier si la commission n'a pas déjà été versée
                            if not lien_parrainage.commission_versee:

                                parrain = lien_parrainage.parrain # L'objet Client du parrain

                                # Calcul et versement
                                commission_montant = int(montant_pack * COMMISSION_RATE)

                                # Mise à jour atomique du solde du parrain (avec F pour sécurité)
                                Client.objects.filter(pk=parrain.pk).update(
                                    solde=F('solde') + commission_montant
                                )

                                # Mise à jour du statut dans la table Parrainage
                                lien_parrainage.commission_versee = True
                                lien_parrainage.save(update_fields=["commission_versee"])

                                messages.info(
                                    request,
                                    f"Commission de parrainage de **{commission_montant} F** versée à votre parrain.",
                                )

                        except Parrainage.DoesNotExist:
                            # Ce cas ne devrait pas arriver si signup_view est correct,
                            # mais nous gérons l'absence de lien.
                            messages.warning(request, "Alerte: Parrain trouvé, mais lien de commission manquant. Contactez le support.")
                        except Exception as e:
                            # Gérer les erreurs spécifiques à la commission
                            messages.warning(request, "Alerte: Commission non versée suite à une erreur technique.")
                            print(f"Erreur Commission Parrainage: {e}")

                    # --- FIN LOGIQUE DE COMMISSION PARRAINAGE ---

                    messages.success(request, f"Félicitations ! Vous avez acheté le pack {pack_to_buy.nomPack} pour {montant_pack} F.")
                    return redirect("mes-packs")

        except Exception as e:
            messages.error(
                request,
                f"Une erreur interne est survenue lors de la transaction. L'achat a été annulé.",
            )
            print(f"Erreur lors de l'achat du pack {pack_id}: {e}")
            return redirect("packs")

    # ... (Reste de la vue) ...
    elif request.method == "POST" and "annuler" in request.POST:
        return redirect("packs")

    return render(request, "finance/buypack_view.html", context)


# CODE POUR VOIR LES PACKS DU CLIENT CONNECTE


@login_required
def mespacks_view(request):
    """
    Récupération des packs (Achats) pour l'utilisateur avec statut d'expiration.
    """
    from django.utils import timezone

    maintenant = timezone.now()
    packs_achats = (
        Achat.objects.filter(
            codeClt_id=request.user.pk,
        )
        .select_related("codePack")
        .order_by("-date_creation")
    )

    mespacks_achats_details = []

    for achat in packs_achats:
        pack_base = achat.codePack
        
        # Calcul du temps restant avant expiration
        if achat.date_expiration is not None:
            temps_avant_expiration = achat.date_expiration - maintenant

            # Formater le statut
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
        mespacks_achats_details.append(
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

    context = {"mespacks_achats": mespacks_achats_details}
    return render(request, "finance/mespacks_view.html", context)


@login_required(login_url="login")
def mesdepots_view(request):
    """
    Récupère et affiche l'historique des dépôts pour le client connecté.
    """
    try:
        depots_utilisateur = Depot.objects.filter(codeClt=request.user.pk).order_by(
            "-date_creation"
        )

    except Exception as e:
        print(f"Erreur lors de la récupération des dépôts: {e}")
        depots_utilisateur = []

    context = {"mesdepots": depots_utilisateur}
    return render(request, "finance/mesdepots_view.html", context)


@login_required
def mesretraits_view(request):
    """
    Affiche l'historique des retraits de l'utilisateur connecté.
    Correction : Utilisation de codeClt_id=request.user.pk pour éviter le ValueError.
    """
    mes_retraits = Retrait.objects.filter(codeClt_id=request.user.pk).order_by(
        "-date_creation"
    )

    context = {
        "mes_retraits": mes_retraits,
    }
    return render(request, "finance/mesretraits_view.html", context)


def politique_controller(request):
    return render(request, "finance/politique_view.html")


def process_expired_packs():
    """
    CRON JOB: Crédite le profit à la fin de la durée du pack (versement en une fois).
    """
    from django.utils import timezone
    
    maintenant = timezone.now()
    achats_expires = (
        Achat.objects.select_for_update()
        .filter(date_expiration__lte=maintenant, profit_versé=False, is_active=True)
        .select_related("codeClt", "codePack")
    )

    if not achats_expires:
        return f"Aucun pack expiré à traiter à {maintenant.strftime('%H:%M:%S')}."

    try:
        with transaction.atomic():
            gains_par_client = {}
            clients_a_sauvegarder = {}
            achats_traites = 0
            total_gains_traites = 0
            
            for achat in achats_expires:
                client = achat.codeClt
                montant_investissement = achat.codePack.montant
                montant_profit = achat.montant_total_profit
                total_versement = montant_investissement + montant_profit

                if client.pk not in gains_par_client:
                    gains_par_client[client.pk] = 0
                    clients_a_sauvegarder[client.pk] = client

                gains_par_client[client.pk] += total_versement
                total_gains_traites += montant_profit
                
                # Marquer le profit comme versé
                achat.profit_versé = True
                achat.is_active = False
                achat.save(update_fields=["profit_versé", "is_active"])
                achats_traites += 1
                
                # Mettre à jour la date d'expiration du dernier pack
                client.last_pack_expiration_date = achat.date_expiration.date()
            
            # Créditer les clients
            for client_pk, gain_total in gains_par_client.items():
                client = clients_a_sauvegarder[client_pk]
                client.solde += gain_total
                client.revenu += total_gains_traites  # Ajouter les profits seulement
                client.save(update_fields=["solde", "revenu", "last_pack_expiration_date"])

        return (
            f"Traitement RÉUSSI. {achats_traites} packs traités. "
            f"Total crédité aux clients: {total_gains_traites} FCFA de profits."
        )

    except Exception as e:
        print(f"Erreur fatale lors du traitement des packs expirés: {e}")
        return f"Traitement ÉCHOUÉ : Une erreur interne est survenue : {e}"


def process_withdrawal_suspensions():
    """
    CRON JOB: Active les suspensions de retrait 12 jours après l'expiration du dernier pack.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    maintenant = timezone.now().date()
    
    # Trouver les clients dont le dernier pack a expiré il y a 12 jours
    date_limite = maintenant - timedelta(days=12)
    
    clients_a_suspendre = Client.objects.filter(
        last_pack_expiration_date=date_limite,
        withdrawal_suspended=False,
        # Vérifier qu'il n'y a plus de packs actifs
    )
    
    suspensions_creees = 0
    
    try:
        with transaction.atomic():
            for client in clients_a_suspendre:
                # Vérifier qu'il n'y a vraiment pas de packs actifs
                if Achat.objects.filter(codeClt=client, is_active=True).exists():
                    continue
                
                # Créer la suspension
                suspension_end = maintenant + timedelta(days=1)  # Suspension d'un jour pour exemple
                WithdrawalSuspension.objects.get_or_create(
                    client=client,
                    defaults={
                        'suspension_start': maintenant,
                        'suspension_end': suspension_end,
                        'reason': '12 jours après expiration du dernier pack',
                    }
                )
                
                # Marquer le client comme ayant des retraits suspendus
                client.withdrawal_suspended = True
                client.save(update_fields=['withdrawal_suspended'])
                suspensions_creees += 1
    
    except Exception as e:
        print(f"Erreur lors du traitement des suspensions: {e}")
        return f"Erreur : {e}"
    
    return f"Suspensions créées : {suspensions_creees}"



def trigger_process_packs_api(request):
    """
    URL Secrète pour exécuter la commande de gestion via HTTP.
    Exemple d'appel : /api/tasks/process-packs/?token=VOTRE_CLE_SECRETE_ICI
    """
    # Définissez un token sécurisé (vous pouvez aussi le mettre dans vos variables d'environnement)
    SECRET_TOKEN = "FortuneFlow_Secured_Cron_Token_2026_XYZ"
    
    # Récupération du token envoyé dans l'URL
    user_token = request.GET.get('token')
    
    if user_token != SECRET_TOKEN:
        return HttpResponseForbidden("Accès non autorisé.")
        
    try:
        # 1. Traitement des packs expirés
        result_packs = process_expired_packs()
        
        # 2. Traitement des suspensions de retraits
        result_suspensions = process_withdrawal_suspensions()
        
        return JsonResponse({
            "status": "success",
            "packs_result": result_packs,
            "suspensions_result": result_suspensions
        }, status=200)
        
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


def admin_required(view_func):
    """Décorateur pour exiger que l'utilisateur soit un administrateur."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_admin
        ):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Accès refusé. Vous devez être administrateur.")

    return wrapper


@admin_required
def admin_dashboard_view(request):

    depots_attente_count = Depot.objects.all().count()
    retraits_attente_count = Retrait.objects.all().count()
    # Utiliser Sum de Django pour agréger correctement le champ 'revenu'
    revenu_genere = Client.objects.aggregate(total=Sum('revenu'))['total'] or 0

    context = {
        "total_clients": Client.objects.count(),
        "all_depots": depots_attente_count,
        "all_retraits": retraits_attente_count,
        "total_revenue": revenu_genere,
    }
    return render(request, "finance/admin_dashboard.html", context)


@login_required(login_url="login")
@user_passes_test(is_superuser, login_url="accueil")
def valdep_view(request):
    """
    Affiche la liste des dépôts en attente pour l'administrateur.
    """
    depots_en_attente = Depot.objects.all().order_by(
        "date_creation"
    )

    context = {
        "result": depots_en_attente,
    }
    return render(request, "finance/valDep_view.html", context)


@login_required(login_url="login")
@user_passes_test(is_superuser, login_url="accueil")
def valider_depot_action(request, codeDepot):
    """
    Gère la validation (crédit du solde) ou l'annulation d'un dépôt.
    """
    depot = get_object_or_404(Depot, codeDepot=codeDepot)

    if request.method == "POST":
        if depot.statut.lower() != "en attente":
            messages.error(request, "Ce dépôt a déjà été traité.")
            return redirect("valider-depot")

        action = request.POST.get("action")

        try:
            with transaction.atomic():

                if action == "valider":
                    Client.objects.filter(
                        pk=depot.codeClt.pk
                    ).select_for_update().update(solde=F("solde") + depot.montant)
                    depot.statut = "validé"
                    depot.save(update_fields=["statut"])

                    messages.success(
                        request,
                        f"Dépôt de **{depot.montant} F** du client {depot.codeClt.nomClt} validé. Solde mis à jour.",
                    )

                elif action == "annuler":
                    depot.statut = "annulé"
                    depot.save(update_fields=["statut"])

                    messages.warning(
                        request, f"Dépôt du client {depot.codeClt.nomClt} annulé."
                    )

                else:
                    messages.error(request, "Action non reconnue.")

            return redirect("valider-depot")

        except Exception as e:
            error_message = f"Erreur critique: {e.__class__.__name__}: {e}"
            print(error_message)
            messages.error(
                request,
                f"Erreur lors de la mise à jour de la transaction ou du solde client. Détail: {e.__class__.__name__}",
            )

            return redirect("valider-depot")
    context = {
        "depot": depot,
    }
    return render(request, "finance/popup_depot_action.html", context)


@login_required(login_url="login")
@user_passes_test(is_superuser, login_url="accueil")
def valretrait_view(request):
    """
    Affiche la liste des retraits ayant le statut 'en attente'.
    """
    retraits_en_attente = Retrait.objects.all().order_by(
        "date_creation"
    )

    context = {
        "result": retraits_en_attente,
    }
    return render(request, "finance/valRetrait_view.html", context)


@login_required(login_url="login")
@user_passes_test(is_superuser, login_url="accueil")
def valider_retrait_action(request, codeRetrait):
    """
    Gère la validation ou l'annulation d'un retrait spécifique.
    """
    retrait = get_object_or_404(Retrait, codeRetrait=codeRetrait)

    if request.method == "POST":

        if retrait.statut != "en attente":
            messages.error(request, "Ce retrait a déjà été traité.")
            return redirect("valider-retrait")

        action = request.POST.get("action")

        try:
            with transaction.atomic():

                if action == "valider":
                    retrait.statut = "validé"
                    retrait.save(update_fields=["statut"])

                    messages.success(
                        request,
                        f"Retrait du client {retrait.codeClt.nomClt} (Net: {retrait.montant} F) validé.",
                    )

                elif action == "annuler":
                    FRAIS_POURCENTAGE_RETRAIT = 0.10

                    montant_brut_a_rembourser = int(
                        retrait.montant / (1.0 - FRAIS_POURCENTAGE_RETRAIT)
                    )
                    Client.objects.filter(
                        pk=retrait.codeClt.pk
                    ).select_for_update().update(
                        solde=F("solde") + montant_brut_a_rembourser
                    )
                    retrait.statut = "annulé"
                    retrait.save(update_fields=["statut"])

                    messages.warning(
                        request,
                        f"Retrait du client {retrait.codeClt.nomClt} annulé. Montant BRUT ({montant_brut_a_rembourser} F) remboursé.",
                    )

                else:
                    messages.error(request, "Action non reconnue.")

            return redirect("valider-retrait")

        except Exception as e:
            print(f"Erreur critique lors de l'action de retrait: {e}")
            messages.error(
                request,
                "Erreur lors de la mise à jour de la transaction ou du solde client.",
            )
            return redirect("valider-retrait")
    context = {
        "retrait": retrait,
    }
    return render(request, "finance/popup_retrait_action.html", context)


@admin_required
def user_view(request):
    clients = Client.objects.all().order_by("-date_creation")
    context = {"clients": clients}
    return render(request, "finance/user_view.html", context)


@admin_required
def withdrawal_suspensions_view(request):
    """
    Affiche la liste des suspensions de retrait actives.
    """
    from .models import WithdrawalSuspension
    
    suspensions = WithdrawalSuspension.objects.all().order_by("-suspension_start")
    context = {
        "suspensions": suspensions,
    }
    return render(request, "finance/withdrawal_suspensions_view.html", context)
