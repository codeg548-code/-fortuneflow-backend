import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_alter_retrait_statut'),
    ]

    operations = [
        migrations.AddField(
            model_name='achat',
            name='cycles_restants',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='achat',
            name='prochain_revenu_du',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='achat',
            name='date_creation',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
