from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from .models import Achat, Client, Pack


class PackViewTests(TestCase):
    def setUp(self):
        self.pack = Pack.objects.create(
            nomPack="Starter",
            montant=1000,
            gainJr=10,
            duree=30,
        )

    def test_pack_view_exposes_pack_details_for_template(self):
        response = self.client.get(reverse("packs"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("packs_detail", response.context)
        self.assertEqual(len(response.context["packs_detail"]), 1)
        self.assertEqual(response.context["packs_detail"][0]["pack"], self.pack)
        self.assertTrue(response.context["packs_detail"][0]["peut_acheter"])


class BuyPackViewTests(TestCase):
    def setUp(self):
        self.user = Client.objects.create(
            codeClt=1,
            numero="670000001",
            nomClt="Test User",
            mdp=make_password("12345678"),
            solde=5000,
        )
        self.pack = Pack.objects.create(
            nomPack="Premium",
            montant=1000,
            gainJr=20,
            duree=45,
        )

    def test_buy_pack_view_exposes_purchase_state_for_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("buy-pack", args=[self.pack.codePack]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["peut_acheter"])
        self.assertEqual(response.context["message_blocage"], "")


class RetraitViewTests(TestCase):
    def setUp(self):
        self.user = Client.objects.create(
            codeClt=2,
            numero="670000002",
            nomClt="Retrait User",
            mdp=make_password("12345678"),
            solde=10000,
            moyen_paiement="MTN",
            nom_beneficiaire="Test Beneficiaire",
            numero_portefeuille="670000003",
        )
        self.pack = Pack.objects.create(
            nomPack="Basic",
            montant=5000,
            gainJr=5,
            duree=30,
        )
        Achat.objects.create(codeClt=self.user, codePack=self.pack)

    def test_retrait_view_treats_complete_payment_details_as_configured(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("retrait"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["carte_configuree"])
        self.assertNotContains(response, "Carte de paiement requise")
