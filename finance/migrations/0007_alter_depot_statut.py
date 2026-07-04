from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_client_commission_versee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='depot',
            name='statut',
            field=models.CharField(default='en attente', max_length=20, unique=True),
        ),
    ]
