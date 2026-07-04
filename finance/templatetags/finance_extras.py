from django import template
from django.templatetags.static import static

register = template.Library()

PACK_IMAGES = {
    "ROCK": "acheterpack.png",
    "IRON": "cuivre.png",
    "IRON++": "cuivres.png",
    "BRONZE": "bronze.png",
    "BRONZE++": "bronzes.png",
    "SILVER": "silver.png",
    "SILVER++": "silvers.png",
    "GOLD": "gold.png",
    "GOLD++": "golds.png",
    "DIAMOND": "diamond.png",
    "DIAMOND++": "diamonds.png",
    "PLATINUM": "platinum.png",
    "PLATINUM++": "platinums.png",
}


@register.simple_tag
def pack_image(nom_pack):
    filename = PACK_IMAGES.get(nom_pack, "default_pack.png")
    return static(f"finance/images/{filename}")
