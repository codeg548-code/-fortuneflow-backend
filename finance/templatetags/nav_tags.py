from django import template

register = template.Library()

NAV_GROUPS = {
    "accueil": {"accueil"},
    "packs": {"packs", "buy-pack", "buy-pack-global", "mes-packs"},
    "depot": {"depot", "mes-depots"},
    "retrait": {"retrait", "mes-retraits"},
    "compte": {"compte", "parrainage", "politique"},
}


@register.simple_tag(takes_context=True)
def nav_active(context, group):
    url_name = context.get("request").resolver_match.url_name
    return "active" if url_name in NAV_GROUPS.get(group, set()) else ""
