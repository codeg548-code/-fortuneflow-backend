from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_achat_cycles_restants_achat_prochain_revenu_du_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='commission_versee',
            field=models.BooleanField(default=False),
        ),
    ]
