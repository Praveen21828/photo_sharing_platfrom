import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from events.models import Event


class Photo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='photos')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_photos',
    )
    filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=1024, unique=True)
    file_size = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', '-created_at']),
            models.Index(fields=['uploaded_by', '-created_at']),
        ]

    def clean(self):
        if self.uploaded_by_id and (
            not self.uploaded_by.is_active
            or self.uploaded_by.role not in self.uploaded_by.Role.values
        ):
            raise ValidationError({'uploaded_by': 'The uploader must be an active platform user.'})

    def __str__(self):
        return self.filename