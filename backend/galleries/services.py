import hashlib
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from photos.models import Photo

from .models import Gallery, GalleryAccessToken, GalleryPhoto


def create_gallery(event, pin):
    if not pin or len(str(pin)) < 4:
        raise ValidationError('A gallery PIN must be at least 4 characters long.')

    public_identifier = secrets.token_urlsafe(24)
    while Gallery.objects.filter(public_identifier=public_identifier).exists():
        public_identifier = secrets.token_urlsafe(24)

    return Gallery.objects.create(
        event=event,
        public_identifier=public_identifier,
        pin_hash=make_password(str(pin)),
    )


@transaction.atomic
def select_photo(gallery, photo_id):
    if gallery.published:
        raise ValidationError('Published galleries cannot be modified.')

    try:
        photo = Photo.objects.get(id=photo_id, event=gallery.event)
    except Photo.DoesNotExist as exc:
        raise ValidationError('Photo does not belong to this gallery event.') from exc

    if gallery.gallery_photos.filter(photo=photo).exists():
        raise ValidationError('Photo is already selected for this gallery.')

    return GalleryPhoto.objects.create(gallery=gallery, photo=photo)


@transaction.atomic
def deselect_photo(gallery, photo_id):
    if gallery.published:
        raise ValidationError('Published galleries cannot be modified.')

    selection = gallery.gallery_photos.filter(photo_id=photo_id).first()
    if selection is None:
        raise ValidationError('Selected photo not found in this gallery.')

    selection.delete()
    return True


def publish_gallery(gallery):
    if gallery.published:
        return gallery
    if not gallery.gallery_photos.exists():
        raise ValidationError('A gallery must contain at least one selected photo before publishing.')
    gallery.published = True
    gallery.published_at = timezone.now()
    gallery.save(update_fields=['published', 'published_at'])
    return gallery


def verify_gallery_pin(gallery, pin):
    if not gallery.published:
        return None

    if not check_password(pin, gallery.pin_hash):
        return None

    raw_token = secrets.token_urlsafe(32)
    GalleryAccessToken.objects.create(
        gallery=gallery,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
    )
    return raw_token


def get_gallery_by_access_token(public_identifier, raw_token):
    if not raw_token:
        return None

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    try:
        access_token = GalleryAccessToken.objects.select_related('gallery').get(
            token_hash=token_hash,
            gallery__public_identifier=public_identifier,
        )
    except GalleryAccessToken.DoesNotExist:
        return None

    if not access_token.gallery.published:
        return None

    return access_token.gallery