from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_client_is_active_client_is_admin_client_password_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='retrait',
            name='statut',
            field=models.CharField(default='en attente', max_length=25),
        ),
    ]
