import datetime

from django.utils import timezone
from rest_framework import serializers

from .models import Client, Pack, Depot, Retrait, Parrainage, Achat, WithdrawalSuspension, ReferralInfo


class FlexibleDateField(serializers.DateField):
    """Accepte date ou datetime (MySQL + default timezone.now sur DateField)."""

    def to_representation(self, value):
        if isinstance(value, datetime.datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            value = value.date()
        return super().to_representation(value)


class ClientSerializer(serializers.ModelSerializer):
    can_withdraw = serializers.SerializerMethodField()
    can_refer = serializers.SerializerMethodField()
    date_creation = FlexibleDateField(read_only=True)
    last_pack_expiration_date = FlexibleDateField(read_only=True)
    
    class Meta:
        model = Client
        fields = [
            'codeClt',
            'nomClt',
            'numero',
            'solde',
            'revenu',
            'codeParrain',
            'statut',
            'date_creation',
            'moyen_paiement',
            'nom_beneficiaire',
            'numero_portefeuille',
            'withdrawal_suspended',
            'last_pack_expiration_date',
            'can_withdraw',
            'can_refer',
        ]
        read_only_fields = [
            'codeClt',
            'solde',
            'revenu',
            'statut',
            'date_creation',
            'withdrawal_suspended',
            'last_pack_expiration_date',
        ]
    
    def get_can_withdraw(self, obj):
        can_withdraw, _ = obj.can_withdraw()
        return can_withdraw
    
    def get_can_refer(self, obj):
        can_refer, _ = obj.can_refer()
        return can_refer


class PackSerializer(serializers.ModelSerializer):
    date_creation = FlexibleDateField(read_only=True)

    class Meta:
        model = Pack
        fields = ['codePack', 'nomPack', 'montant', 'gainJr', 'duree', 'date_creation']


class AchatSerializer(serializers.ModelSerializer):
    codePack = PackSerializer(read_only=True)
    codeClt = ClientSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = Achat
        fields = [
            'codeAchat',
            'codeClt',
            'codePack',
            'date_creation',
            'date_expiration',
            'montant_total_profit',
            'profit_versé',
            'is_active',
            'is_expired',
        ]
        read_only_fields = [
            'codeAchat',
            'date_creation',
            'date_expiration',
            'montant_total_profit',
            'profit_versé',
            'is_active',
        ]
    
    def get_is_expired(self, obj):
        return obj.is_expired()


class DepotSerializer(serializers.ModelSerializer):
    date_creation = FlexibleDateField(read_only=True)

    class Meta:
        model = Depot
        fields = ['codeDepot', 'codeClt', 'nomNum', 'numDepot', 'montant', 'idTransaction', 'statut', 'date_creation']
        read_only_fields = ['codeDepot', 'statut', 'date_creation']


class RetraitSerializer(serializers.ModelSerializer):
    date_creation = FlexibleDateField(read_only=True)

    class Meta:
        model = Retrait
        fields = ['codeRetrait', 'codeClt', 'montant', 'statut', 'date_creation']
        read_only_fields = ['codeRetrait', 'statut', 'date_creation']


class ParrainageSerializer(serializers.ModelSerializer):
    parrain = ClientSerializer(read_only=True)
    filleul = ClientSerializer(read_only=True)
    date_creation = FlexibleDateField(read_only=True)

    class Meta:
        model = Parrainage
        fields = ['id', 'parrain', 'filleul', 'commission_versee', 'date_creation']


class WithdrawalSuspensionSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    is_active = serializers.SerializerMethodField()
    suspension_start = FlexibleDateField(read_only=True)
    suspension_end = FlexibleDateField(read_only=True)
    
    class Meta:
        model = WithdrawalSuspension
        fields = [
            'suspension_id',
            'client',
            'suspension_start',
            'suspension_end',
            'reason',
            'is_active',
        ]
        read_only_fields = ['suspension_id', 'client']
    
    def get_is_active(self, obj):
        return obj.is_active()


class ReferralInfoSerializer(serializers.ModelSerializer):
    sponsor = ClientSerializer(read_only=True)
    sponsored_client = ClientSerializer(read_only=True)
    date_creation = FlexibleDateField(read_only=True)

    class Meta:
        model = ReferralInfo
        fields = [
            'referral_id',
            'sponsor',
            'sponsored_client',
            'commission_amount',
            'commission_paid',
            'date_creation',
        ]
        read_only_fields = [
            'referral_id',
            'sponsor',
            'sponsored_client',
            'commission_paid',
        ]
