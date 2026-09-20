from rest_framework.permissions import BasePermission


class IsEventAdmin(BasePermission):
    message = 'Only the Admin/Lead who owns this event can perform this action.'

    def has_object_permission(self, request, view, obj):
        return request.user.role == request.user.Role.ADMIN and obj.created_by_id == request.user.id