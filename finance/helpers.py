def mask_phone(numero):
    """Masque un numéro pour affichage (ex: 670123456 → 670 *** **56)."""
    if not numero:
        return "—"
    digits = "".join(c for c in str(numero) if c.isdigit())
    if len(digits) < 4:
        return "***"
    return f"{digits[:3]} *** **{digits[-2:]}"


def phone_last_digits(numero, count=4):
    """Retourne les N derniers chiffres d'un numéro."""
    digits = "".join(c for c in str(numero) if c.isdigit())
    return digits[-count:] if len(digits) >= count else digits


def parrainage_link(request, client):
    """Lien de parrainage au format URL correct (/signup/<code>/)."""
    return f"http://{request.get_host()}/#/signup/{client.pk}/"


def client_has_payment_info(client):
    return bool(client.numero_portefeuille and client.nom_beneficiaire)


def pack_est_achat_unique(pack):
    from .constants import PACK_NOM_ACHAT_UNIQUE
    achat_unique = getattr(pack, "achat_unique", False)
    return achat_unique or pack.nomPack == PACK_NOM_ACHAT_UNIQUE


def client_a_deja_achete_pack(client, pack):
    from .models import Achat
    return Achat.objects.filter(codeClt=client, codePack=pack).exists()


def pack_est_en_stock(pack):
    """Vérifie si un pack a encore du stock disponible."""
    try:
        stock_disponible = getattr(pack, "stock_disponible", None)
        if stock_disponible is None:
            return True
        return int(stock_disponible) > 0
    except (TypeError, ValueError):
        return True


def pack_peut_etre_achete(client, pack):
    """Retourne (autorisé, message d'erreur)."""
    if not pack_est_en_stock(pack):
        return False, "Ce pack est épuisé."
    if client and pack_est_achat_unique(pack) and client_a_deja_achete_pack(client, pack):
        return False, "Vous avez déjà acheté ce pack."
    return True, ""


def enrichir_packs_pour_client(packs, client=None):
    """Ajoute les flags d'achat/stock pour l'affichage liste."""
    result = []
    for pack in packs:
        est_en_stock = pack_est_en_stock(pack)
        peut_acheter, message = pack_peut_etre_achete(client, pack) if client else (est_en_stock, "")
        if not client and not est_en_stock:
            peut_acheter, message = False, "Stock épuisé."
        deja_achete = client_a_deja_achete_pack(client, pack) if client else False
        result.append({
            "pack": pack,
            "peut_acheter": peut_acheter,
            "message_blocage": message,
            "deja_achete": deja_achete,
            "est_en_stock": est_en_stock,
            "stock_disponible": getattr(pack, "stock_disponible", None),
            "stock_initial": getattr(pack, "stock_initial", None),
        })
    return result


def invalidate_user_cache(user_id):
    """
    Invalide le cache du dashboard de l'utilisateur.
    À appeler dès qu'une opération modifie le solde ou le revenu du client.
    """
    if user_id:
        cache.delete(f"user_dashboard_{user_id}")
