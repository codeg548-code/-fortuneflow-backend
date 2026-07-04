from django.db import migrations


def init_pack_stock(apps, schema_editor):
    Pack = apps.get_model("finance", "Pack")
    for pack in Pack.objects.all():
        updated = []
        if pack.stock_initial == 0 and pack.stock_disponible == 0:
            pack.stock_initial = 100
            pack.stock_disponible = 100
            updated.extend(["stock_initial", "stock_disponible"])
        if pack.nomPack == "STD-2500" and not pack.achat_unique:
            pack.achat_unique = True
            updated.append("achat_unique")
        if updated:
            pack.save(update_fields=updated)


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0012_pack_stock"),
    ]

    operations = [
        migrations.RunPython(init_pack_stock, migrations.RunPython.noop),
    ]
