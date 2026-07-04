from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthenticatedClient(BasePermission):
    """Autorise uniquement les clients authentifiés (modèle Client)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "codeClt")
        )


class IsAdminClient(BasePermission):
    """Autorise les clients avec droits administrateur."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "is_admin")
            and (user.is_admin or user.is_staff)
        )


class ReadOnlyOrAdmin(BasePermission):
    """Lecture publique, écriture réservée aux admins."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "is_admin")
            and (user.is_admin or user.is_staff)
        )
