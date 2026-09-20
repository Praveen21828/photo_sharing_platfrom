from django.urls import path

from .views import EventDetailView, EventListCreateView, EventMemberListCreateView

urlpatterns = [
    path('', EventListCreateView.as_view(), name='event-list-create'),
    path('<uuid:event_id>/', EventDetailView.as_view(), name='event-detail'),
    path('<uuid:event_id>/members/', EventMemberListCreateView.as_view(), name='event-members'),
]