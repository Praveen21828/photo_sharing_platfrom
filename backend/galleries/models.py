import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from events.models import Event
from photos.models import Photo


class Gallery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='galleries')
    public_identifier = models.CharField(max_length=64, unique=True, db_index=True)
    pin_hash = models.CharField(max_length=128)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(published=False, published_at__isnull=True) | Q(published=True, published_at__isnull=False)),
                name='gallery_published_timestamp_consistent',
            ),
        ]
        indexes = [
            models.Index(fields=['event', 'published']),
        ]

    def __str__(self):
        return self.public_identifier


class GalleryPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name='gallery_photos')
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='gallery_selections')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['gallery', 'photo'], name='unique_gallery_photo'),
        ]
        indexes = [
            models.Index(fields=['gallery', 'created_at']),
            models.Index(fields=['photo', 'gallery']),
        ]

    def clean(self):
        if self.gallery_id and self.photo_id:
            gallery_event_id = self.gallery.event_id
            photo_event_id = self.photo.event_id
            if gallery_event_id != photo_event_id:
                raise ValidationError('A gallery can contain photos only from its event.')

    def __str__(self):
        return f'{self.gallery} - {self.photo}'



class GalleryAccessToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name='access_tokens',
    )
    token_hash = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['gallery', 'created_at']),
        ]

    def __str__(self):
        return f'{self.gallery.public_identifier} - {self.id}'