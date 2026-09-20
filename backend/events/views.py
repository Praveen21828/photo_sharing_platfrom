from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import IsAdmin
from core.responses import success_response

from .models import Event, EventMember
from .permissions import IsEventAdmin
from .serializers import EventMemberSerializer, EventSerializer


def visible_events(user):
    if user.role == user.Role.ADMIN:
        return Event.objects.filter(created_by=user)
    return Event.objects.filter(memberships__user=user)


class EventListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(EventSerializer(visible_events(request.user), many=True).data)

    def post(self, request):
        if request.user.role != request.user.Role.ADMIN:
            self.permission_denied(request, message='Admin/Lead access is required.')
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(created_by=request.user)
        return success_response(EventSerializer(event).data, status.HTTP_201_CREATED)


class EventDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, event_id):
        return get_object_or_404(visible_events(request.user), id=event_id)

    def get(self, request, event_id):
        return success_response(EventSerializer(self.get_object(request, event_id)).data)

    def patch(self, request, event_id):
        event = self.get_object(request, event_id)
        self.check_object_permissions(request, event)
        serializer = EventSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return success_response(EventSerializer(serializer.save()).data)

    def check_object_permissions(self, request, event):
        if not IsEventAdmin().has_object_permission(request, self, event):
            self.permission_denied(request, message=IsEventAdmin.message)


class EventMemberListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_event(self, request, event_id):
        event = get_object_or_404(visible_events(request.user), id=event_id)
        return event

    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        queryset = event.memberships.select_related('user').all()
        return success_response(EventMemberSerializer(queryset, many=True).data)

    def post(self, request, event_id):
        event = get_object_or_404(visible_events(request.user), id=event_id)
        if event.created_by_id != request.user.id or request.user.role != request.user.Role.ADMIN:
            self.permission_denied(request, message='Only the event owner can assign Team Members.')
        serializer = EventMemberSerializer(data=request.data, context={'event': event})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                membership = serializer.save()
        except IntegrityError:
            return success_response({'code': 'conflict', 'message': 'Team Member is already assigned.'}, status.HTTP_409_CONFLICT)
        return success_response(EventMemberSerializer(membership).data, status.HTTP_201_CREATED)