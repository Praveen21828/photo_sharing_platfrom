from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    message = 'Admin/Lead access is required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role == request.user.Role.ADMIN)


class IsTeamMember(BasePermission):
    message = 'Team Member access is required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.role == request.user.Role.TEAM_MEMBER)