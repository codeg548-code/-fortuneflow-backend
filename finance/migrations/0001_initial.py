import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Pack',
            fields=[
                ('codePack', models.AutoField(primary_key=True, serialize=False)),
                ('nomPack', models.CharField(max_length=20)),
                ('montant', models.IntegerField()),
                ('gainJr', models.IntegerField()),
                ('duree', models.IntegerField()),
                ('date_creation', models.DateField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': "Pack d'Investissement",
                'verbose_name_plural': "Packs d'Investissement",
            },
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('codeClt', models.IntegerField(primary_key=True, serialize=False)),
                ('nomClt', models.CharField(blank=True, max_length=20, null=True)),
                ('numero', models.CharField(max_length=20, unique=True)),
                ('mdp', models.CharField(max_length=20)),
                ('solde', models.IntegerField(default=0)),
                ('revenu', models.IntegerField(default=0)),
                ('codeParrain', models.IntegerField(default=0)),
                ('statut', models.IntegerField(default=0)),
                ('date_creation', models.DateField(default=django.utils.timezone.now)),
                ('parrain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fillots', to='finance.client')),
            ],
            options={
                'verbose_name': 'Client',
                'verbose_name_plural': 'Clients',
            },
        ),
        migrations.CreateModel(
            name='Depot',
            fields=[
                ('codeDepot', models.AutoField(primary_key=True, serialize=False)),
                ('nomNum', models.CharField(blank=True, max_length=25, null=True)),
                ('numDepot', models.IntegerField(blank=True, null=True)),
                ('montant', models.IntegerField()),
                ('idTransaction', models.CharField(max_length=20, unique=True)),
                ('statut', models.IntegerField(default=0)),
                ('date_creation', models.DateField(default=django.utils.timezone.now)),
                ('codeClt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.client')),
            ],
            options={
                'verbose_name': 'Dépôt',
                'verbose_name_plural': 'Dépôts',
            },
        ),
        migrations.CreateModel(
            name='Achat',
            fields=[
                ('codeAchat', models.AutoField(primary_key=True, serialize=False)),
                ('date_creation', models.DateField(default=django.utils.timezone.now)),
                ('codeClt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.client')),
                ('codePack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.pack')),
            ],
            options={
                'verbose_name': 'Achat de Pack',
                'verbose_name_plural': 'Achats de Packs',
            },
        ),
        migrations.CreateModel(
            name='Retrait',
            fields=[
                ('codeRetrait', models.AutoField(primary_key=True, serialize=False)),
                ('nomNum', models.CharField(blank=True, max_length=25, null=True)),
                ('numRetrait', models.IntegerField(blank=True, null=True)),
                ('montant', models.IntegerField()),
                ('statut', models.IntegerField()),
                ('date_creation', models.DateField(default=django.utils.timezone.now)),
                ('codeClt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.client')),
            ],
            options={
                'verbose_name': 'Retrait',
                'verbose_name_plural': 'Retraits',
            },
        ),
    ]
