from django.contrib import admin
from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
import csv

from .models import ConfigurationPaiement

from .models import Pack, Client, Depot, Retrait, Achat, Parrainage
from .models import WithdrawalWindow, WithdrawalSuspension, ReferralInfo
from .constants import PARRAINAGE_FIRST_COMMISSION_RATE
from django.urls import path
from django.shortcuts import render
from django.db.models import F
from django.db.models import Sum



@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = (
        "nomPack", "montant", "gainJr", "duree",
        "date_creation",
    )
    search_fields = ("nomPack",)
    ordering = ("montant",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("codeClt", "nomClt", "numero", "solde", "revenu", "is_active", "date_creation")
    search_fields = ("nomClt", "numero", "codeClt")
    list_filter = ("is_active", "is_admin")
    readonly_fields = ("codeClt",)
    actions = ("set_active", "set_inactive", "export_selected_clients")

    def set_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} compte(s) activé(s).")
    set_active.short_description = "Activer les comptes sélectionnés"

    def set_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} compte(s) désactivé(s).")
    set_inactive.short_description = "Désactiver les comptes sélectionnés"

    def export_selected_clients(self, request, queryset):
        """Export selected clients to CSV."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=clients_export.csv"
        writer = csv.writer(response)
        writer.writerow(["codeClt", "nomClt", "numero", "solde", "revenu", "is_active", "date_creation"])
        for c in queryset:
            writer.writerow([c.codeClt, c.nomClt, c.numero, c.solde, c.revenu, c.is_active, c.date_creation])
        return response
    export_selected_clients.short_description = "Exporter les clients sélectionnés (CSV)"


@admin.register(Depot)
class DepotAdmin(admin.ModelAdmin):
    list_display = ("codeDepot", "codeClt", "montant", "idTransaction", "statut", "date_creation")
    list_filter = ("statut",)
    search_fields = ("idTransaction", "codeClt__numero", "codeClt__nomClt")
    actions = ("validate_depots", "reject_depots", "export_selected_depots")

    def validate_depots(self, request, queryset):
        """Validate selected deposits: credit client balance and mark depot validated."""
        count = 0
        for depot in queryset.select_for_update():
            if depot.statut == "validé":
                continue
            try:
                with transaction.atomic():
                    client = Client.objects.select_for_update().get(pk=depot.codeClt.pk)
                    client.solde = client.solde + int(depot.montant)
                    client.save(update_fields=["solde"])
                    depot.statut = "validé"
                    depot.save(update_fields=["statut"])
                    count += 1
            except Exception as e:
                self.message_user(request, f"Erreur lors de la validation du dépôt {depot.codeDepot}: {e}", level="error")
        self.message_user(request, f"{count} dépôt(s) validé(s) et soldes crédités.")
    validate_depots.short_description = "Valider et créditer les dépôts sélectionnés"

    def reject_depots(self, request, queryset):
        updated = queryset.update(statut="annulé")
        self.message_user(request, f"{updated} dépôt(s) marqué(s) comme annulés.")
    reject_depots.short_description = "Marquer les dépôts sélectionnés comme annulés"

    def export_selected_depots(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=depots_export.csv"
        writer = csv.writer(response)
        writer.writerow(["codeDepot", "client", "montant", "idTransaction", "statut", "date_creation"])
        for d in queryset:
            writer.writerow([d.codeDepot, d.codeClt.numero if d.codeClt else '', d.montant, d.idTransaction, d.statut, d.date_creation])
        return response
    export_selected_depots.short_description = "Exporter les dépôts sélectionnés (CSV)"


@admin.register(Retrait)
class RetraitAdmin(admin.ModelAdmin):
    list_display = ("codeRetrait", "codeClt", "montant", "numRetrait", "statut", "date_creation")
    list_filter = ("statut",)
    search_fields = ("codeClt__numero", "numRetrait")
    actions = ("mark_paid", "mark_failed")

    def mark_paid(self, request, queryset):
        updated = queryset.update(statut="payé")
        self.message_user(request, f"{updated} retrait(s) marqué(s) comme payés.")
    mark_paid.short_description = "Marquer les retraits sélectionnés comme payés"

    def mark_failed(self, request, queryset):
        updated = queryset.update(statut="échoué")
        self.message_user(request, f"{updated} retrait(s) marqué(s) comme échoués.")
    mark_failed.short_description = "Marquer les retraits sélectionnés comme échoués"


@admin.register(Achat)
class AchatAdmin(admin.ModelAdmin):
    list_display = ("codeAchat", "codeClt", "codePack", "date_creation", "date_expiration", "profit_versé", "is_active")
    list_filter = ("codePack", "profit_versé", "is_active")
    search_fields = ("codeClt__numero", "codePack__nomPack")


@admin.register(Parrainage)
class ParrainageAdmin(admin.ModelAdmin):
    list_display = ("parrain", "filleul", "commission_versee", "date_creation")
    search_fields = ("parrain__numero", "filleul__numero", "parrain__nomClt", "filleul__nomClt")
    actions = ("mark_commission_paid",)

    def mark_commission_paid(self, request, queryset):
        """Calculate and mark commission as paid for selected parrainage links if not already paid."""
        from django.db.models import F

        count = 0
        for lien in queryset.select_for_update():
            if lien.commission_versee:
                continue
            # compute based on first purchase if any
            premier_achat = Achat.objects.filter(codeClt=lien.filleul).select_related('codePack').order_by('date_creation').first()
            if not premier_achat:
                continue
            montant_pack = premier_achat.codePack.montant
            commission = int(montant_pack * PARRAINAGE_FIRST_COMMISSION_RATE)
            try:
                with transaction.atomic():
                    Client.objects.filter(pk=lien.parrain.pk).update(solde=F('solde') + commission)
                    lien.commission_versee = True
                    lien.save(update_fields=["commission_versee"])
                    count += 1
            except Exception as e:
                self.message_user(request, f"Erreur lors du versement pour lien {lien.pk}: {e}", level="error")
        self.message_user(request, f"{count} commission(s) marquée(s) comme versée et soldes crédités.")
    mark_commission_paid.short_description = "Marquer les commissions sélectionnées comme versées"


@admin.register(WithdrawalWindow)
class WithdrawalWindowAdmin(admin.ModelAdmin):
    list_display = ("start_time", "end_time", "active", "date_creation")
    list_editable = ("active",)
    ordering = ("-date_creation",)


@admin.register(WithdrawalSuspension)
class WithdrawalSuspensionAdmin(admin.ModelAdmin):
    list_display = ("client", "suspension_start", "suspension_end", "reason")
    list_filter = ("suspension_start", "suspension_end")
    search_fields = ("client__nomClt", "client__numero")
    ordering = ("-suspension_start",)
    readonly_fields = ("suspension_start",)


@admin.register(ReferralInfo)
class ReferralInfoAdmin(admin.ModelAdmin):
    list_display = ("sponsor", "sponsored_client", "commission_amount", "commission_paid", "date_creation")
    list_filter = ("commission_paid", "date_creation")
    search_fields = ("sponsor__nomClt", "sponsored_client__nomClt")
    ordering = ("-date_creation",)
    readonly_fields = ("date_creation",)


# --- Admin dashboard view ---
def finance_admin_dashboard(request):
    depots_pending = Depot.objects.filter(statut__iexact='en attente').count()
    retraits_pending = Retrait.objects.filter(statut__iexact='en attente').count()
    commissions_pending = Parrainage.objects.filter(commission_versee=False).count()
    clients_count = Client.objects.count()
    total_packs = Pack.objects.count()
    total_achats = Achat.objects.count()
    packs_low_stock = Pack.objects.filter(stock_disponible__lte=5).order_by('stock_disponible')

    # Total revenue — sum of validated deposits as a baseline metric
    revenue_agg = Depot.objects.filter(statut__iexact='validé').aggregate(total=Sum('montant'))
    total_revenue = revenue_agg['total'] or 0

    context = {
        'all_depots': depots_pending,
        'all_retraits': retraits_pending,
        'total_clients': clients_count,
        'total_revenue': total_revenue,
        'total_packs': total_packs,
        'total_achats': total_achats,
        'packs_low_stock': packs_low_stock,
        'commissions_pending': commissions_pending,
    }
    return render(request, 'finance/admin_dashboard.html', context)


# inject dashboard url into admin
original_get_urls = admin.site.get_urls

def get_urls():
    urls = original_get_urls()
    my_urls = [
        path('dashboard/', admin.site.admin_view(finance_admin_dashboard), name='finance_admin_dashboard'),
    ]
    return my_urls + urls

admin.site.get_urls = get_urls



@admin.register(ConfigurationPaiement)
class ConfigurationPaiementAdmin(admin.ModelAdmin):
    list_display = ("reseau", "numero_reception", "nom_compte", "est_actif", "derniere_modification")
    list_editable = ("numero_reception", "nom_compte", "est_actif")
    list_filter = ("est_actif", "reseau")