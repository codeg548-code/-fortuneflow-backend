from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db.models import F


class Pack(models.Model):
    codePack = models.AutoField(primary_key=True)
    nomPack = models.CharField(max_length=20)
    montant = models.IntegerField()
    gainJr = models.IntegerField()
    duree = models.IntegerField()
    date_creation = models.DateField(default=timezone.now)

    class Meta:
        verbose_name = "Pack d'Investissement"
        verbose_name_plural = "Packs d'Investissement"

    def __str__(self):
        return f"{self.nomPack} ({self.montant} FCFA)"


class ClientManager(BaseUserManager):
    def create_user(self, numero, nomClt, mdp=None, **extra_fields):
        if not numero:
            raise ValueError("Le numéro doit être défini.")

        user = self.model(numero=numero, nomClt=nomClt, **extra_fields)
        user.set_password(mdp)
        user.save(using=self._db)
        return user

    def create_superuser(self, numero, nomClt, mdp=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_admin", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_admin") is not True:
            raise ValueError("Superuser must have is_admin=True.")

        return self.create_user(numero, nomClt, mdp, **extra_fields)


class Client(AbstractBaseUser):
    codeClt = models.IntegerField(primary_key=True)
    nomClt = models.CharField(max_length=20, null=True, blank=True)
    numero = models.CharField(max_length=20, unique=True)
    MOYENS_PAIEMENT = [
        ("MTN", "MTN Mobile Money"),
        ("ORANGE", "Orange Money"),
        ("BANK", "Virement bancaire"),
    ]
    moyen_paiement = models.CharField(
        max_length=20,
        choices=MOYENS_PAIEMENT,
        default="MTN",
        verbose_name="Moyen de paiement",
    )
    nom_beneficiaire = models.CharField(max_length=50, null=True, blank=True)
    numero_portefeuille = models.CharField(max_length=25, null=True, blank=True)
    mdp = models.CharField(max_length=255)
    solde = models.IntegerField(default=0)
    revenu = models.IntegerField(default=0)
    codeParrain = models.IntegerField(default=0)
    statut = models.IntegerField(default=0)
    date_creation = models.DateField(default=timezone.now)
    # commission_versee = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    last_pack_expiration_date = models.DateField(null=True, blank=True, verbose_name="Date d'expiration du dernier pack")
    withdrawal_suspended = models.BooleanField(default=False, verbose_name="Retrait suspendu")
    objects = ClientManager()
    USERNAME_FIELD = "numero"
    REQUIRED_FIELDS = ["nomClt"]
    PASSWORD_FIELD = "mdp"

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.nomClt if self.nomClt else f"Client #{self.codeClt}"

    def has_perm(self, perm, obj=None):
        """Répond si l'utilisateur a une permission spécifique."""
        return self.is_admin

    def has_module_perms(self, app_label):
        """Répond si l'utilisateur a les permissions pour une application donnée."""
        return self.is_admin

    @property
    def is_superuser(self):
        """Nécessaire pour le site d'administration (Admin Site)."""
        return self.is_admin

    @property
    def is_staff(self):
        """Nécessaire pour le site d'administration (Admin Site)."""
        return self.is_admin

    def mettre_a_jour_solde(self, nouveau_solde):
        """Met à jour le solde du client."""
        self.solde = nouveau_solde
        self.save(update_fields=["solde"])
        return True

    def can_withdraw(self):
        """Vérifie si l'utilisateur peut faire un retrait."""
        # Doit avoir acheté un pack
        if not Achat.objects.filter(codeClt=self).exists():
            return False, "Vous devez acheter un pack avant de pouvoir faire un retrait."

        # Vérifier si withdrawals sont suspendus
        if self.withdrawal_suspended:
            return False, "Vos retraits sont suspendus. Veuillez contacter le support manager."

        # Limite de retrait quotidien: 1 retrait par jour
        today = timezone.localdate()
        today_retraits = Retrait.objects.filter(codeClt=self, date_creation=today).count()
        if today_retraits >= 1:
            return False, "Vous ne pouvez effectuer qu'un seul retrait par jour."

        return True, "Retrait autorisé."

    def can_refer(self):
        """Vérifie si l'utilisateur peut parrainer quelqu'un."""
        # Doit avoir acheté un pack
        if not Achat.objects.filter(codeClt=self).exists():
            return False, "Vous devez acheter un pack avant de pouvoir parrainer quelqu'un."
        
        return True, "Parrainage autorisé."


class Parrainage(models.Model):
    # L'utilisateur qui a parrainé (celui qui touche la commission)
    parrain = models.ForeignKey(
        Client, 
        on_delete=models.CASCADE, 
        related_name='filleuls_parraines',
        verbose_name="Parrain"
    )
    
    # L'utilisateur parrainé (celui qui déclenche la commission)
    filleul = models.OneToOneField( # Un filleul ne peut avoir qu'un seul parrain
        Client, 
        on_delete=models.CASCADE, 
        related_name='lien_parrainage',
        verbose_name="Filleul"
    )
    
    # Statut de la commission pour CETTE relation spécifique (0/False: Non versée, 1/True: Versée)
    commission_versee = models.BooleanField(default=False)
    
    date_creation = models.DateField(default=timezone.now)

    class Meta:
        verbose_name = "Lien de Parrainage"
        verbose_name_plural = "Liens de Parrainage"

    def __str__(self):
        statut = "Versée" if self.commission_versee else "En Attente"
        return f"Parrainage: {self.parrain.codeClt} -> {self.filleul.codeClt} ({statut})"

class Achat(models.Model):
    codeAchat = models.AutoField(primary_key=True)
    codeClt = models.ForeignKey("Client", on_delete=models.CASCADE)
    codePack = models.ForeignKey(Pack, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(default=timezone.now)
    date_expiration = models.DateTimeField(null=True, blank=True, verbose_name="Date d'expiration du pack")
    montant_total_profit = models.IntegerField(default=0, verbose_name="Montant total des profits")
    profit_versé = models.BooleanField(default=False, verbose_name="Profit versé")
    is_active = models.BooleanField(default=True, verbose_name="Pack actif")

    class Meta:
        verbose_name = "Achat de Pack"
        verbose_name_plural = "Achats de Packs"

    def __str__(self):
        return f"Achat {self.codeAchat} - {self.codePack.nomPack} par {self.codeClt.codeClt}"

    def save(self, *args, **kwargs):
        if not self.pk:
            maintenant = timezone.now()
            # Calcul de la date d'expiration basée sur la durée du pack (en jours)
            self.date_expiration = maintenant + timedelta(days=self.codePack.duree)
            # Calcul du montant total des profits
            self.montant_total_profit = self.codePack.gainJr * self.codePack.duree

        super().save(*args, **kwargs)

    def is_expired(self):
        """Vérifie si le pack a expiré."""
        return bool(self.date_expiration and timezone.now() >= self.date_expiration)

    def verser_profit(self):
        """Verse le profit total à la fin du pack."""
        if self.is_expired() and not self.profit_versé:
            # Ajouter le montant d'investissement + les profits au solde
            total_a_verser = self.codePack.montant + self.montant_total_profit
            self.codeClt.solde += total_a_verser
            self.codeClt.revenu += self.montant_total_profit
            self.profit_versé = True
            self.is_active = False
            self.save(update_fields=["profit_versé", "is_active"])
            self.codeClt.save(update_fields=["solde", "revenu"])
            return True
        return False


class Depot(models.Model):
    codeDepot = models.AutoField(primary_key=True)
    codeClt = models.ForeignKey(Client, on_delete=models.CASCADE)
    nomNum = models.CharField(max_length=25, null=True, blank=True)
    numDepot = models.IntegerField(null=True, blank=True)
    montant = models.IntegerField()
    idTransaction = models.CharField(max_length=20, unique=True)
    statut = models.CharField(max_length=20, default="en attente")
    date_creation = models.DateField(default=timezone.now)

    class Meta:
        verbose_name = "Dépôt"
        verbose_name_plural = "Dépôts"

    def __str__(self):
        return f"Dépôt #{self.codeDepot} de {self.montant} par {self.codeClt.codeClt} - Statut: {self.statut}"


class Retrait(models.Model):
    codeRetrait = models.AutoField(primary_key=True)
    codeClt = models.ForeignKey(Client, on_delete=models.CASCADE)
    nomNum = models.CharField(max_length=25, null=True, blank=True)
    numRetrait = models.IntegerField(null=True, blank=True)
    montant = models.IntegerField()
    statut = models.CharField(max_length=25, default="en attente")
    date_creation = models.DateField(default=timezone.now)

    class Meta:
        verbose_name = "Retrait"
        verbose_name_plural = "Retraits"

    def __str__(self):
        return f"Retrait #{self.codeRetrait} de {self.montant} par {self.codeClt.codeClt} - Statut: {self.statut}"

    def save(self, *args, **kwargs):
        # Validation avant la création d'un retrait
        if not self.pk:
            # Vérifier que le client a un pack actif
            can_withdraw, message = self.codeClt.can_withdraw()
            if not can_withdraw:
                raise ValueError(message)
            
            # Vérifier que le montant est un multiple de 100
            if self.montant % 100 != 0:
                raise ValueError("Le montant doit être un multiple de 100.")
            
            # Vérifier que le solde du client est suffisant
            if self.codeClt.solde < self.montant:
                raise ValueError("Solde insuffisant pour ce retrait.")

        super().save(*args, **kwargs)


class WithdrawalSuspension(models.Model):
    """Modèle pour tracker les suspensions de retrait des clients."""
    suspension_id = models.AutoField(primary_key=True)
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='withdrawal_suspension')
    suspension_start = models.DateField(default=timezone.now, verbose_name="Date de début de suspension")
    suspension_end = models.DateField(verbose_name="Date de fin de suspension")
    reason = models.TextField(default="12 jours après expiration du dernier pack", verbose_name="Raison")
    
    class Meta:
        verbose_name = "Suspension de Retrait"
        verbose_name_plural = "Suspensions de Retrait"
    
    def __str__(self):
        return f"Suspension de {self.client.codeClt} jusqu'au {self.suspension_end}"
    
    def is_active(self):
        """Vérifie si la suspension est toujours active."""
        return timezone.now().date() <= self.suspension_end


class ReferralInfo(models.Model):
    """Modèle pour tracker les informations de parrainage professionnel."""
    referral_id = models.AutoField(primary_key=True)
    sponsor = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sponsored_clients', verbose_name="Parrain")
    sponsored_client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sponsor_info', verbose_name="Client parrainé")
    commission_amount = models.IntegerField(default=0, verbose_name="Montant de la commission")
    commission_paid = models.BooleanField(default=False, verbose_name="Commission payée")
    date_creation = models.DateField(default=timezone.now, verbose_name="Date de création")
    
    class Meta:
        verbose_name = "Information de Parrainage"
        verbose_name_plural = "Informations de Parrainage"
        unique_together = ('sponsor', 'sponsored_client')
    
    def __str__(self):
        return f"Parrainage: {self.sponsor.codeClt} -> {self.sponsored_client.codeClt}"


class WithdrawalWindow(models.Model):
    """Modèle pour définir les fenêtres de retrait."""
    id = models.BigAutoField(auto_created=True, primary_key=True)
    start_time = models.TimeField(help_text="Heure de début (HH:MM)")
    end_time = models.TimeField(help_text="Heure de fin (HH:MM)")
    active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Fenêtre de retrait"
        verbose_name_plural = "Fenêtres de retrait"
    
    def __str__(self):
        return f"Fenêtre de retrait: {self.start_time} - {self.end_time}"
