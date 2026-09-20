import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', '-created_at']),
        ]

    def clean(self):
        if self.created_by_id and self.created_by.role != self.created_by.Role.ADMIN:
            raise ValidationError({'created_by': 'Only Admin/Lead users can create events.'})

    def __str__(self):
        return self.name


class EventMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='event_memberships',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['event', 'user'], name='unique_event_member'),
        ]
        indexes = [
            models.Index(fields=['event', 'user']),
            models.Index(fields=['user', 'event']),
        ]

    def clean(self):
        if self.user_id and self.user.role != self.user.Role.TEAM_MEMBER:
            raise ValidationError({'user': 'Only Team Members can be assigned to events.'})

    def __str__(self):
        return f'{self.user} - {self.event}'