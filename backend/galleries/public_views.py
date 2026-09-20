from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied, Throttled
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.views import APIView

from core.responses import success_response
from photos.services import create_download_url

from .models import Gallery
from .serializers import PublicPhotoSerializer


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = 'Object storage is temporarily unavailable.'
    default_code = 'storage_unavailable'


def gallery_pin_attempt_key(request, public_identifier):
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
    return f'gallery_pin_attempts:{public_identifier}:{client_ip}'


def handle_failed_pin_attempt(request, public_identifier):
    key = gallery_pin_attempt_key(request, public_identifier)
    cache.add(key, 0, timeout=300)
    next_attempts = cache.incr(key)
    if next_attempts >= 5:
        raise Throttled(detail='Too many incorrect PIN attempts. Please try again later.')
    return next_attempts


def published_gallery(public_identifier):
    return get_object_or_404(
        Gallery.objects.prefetch_related('gallery_photos__photo'),
        public_identifier=public_identifier,
        published=True,
    )


def gallery_token(request, gallery):
    token_value = request.headers.get('X-Gallery-Token')
    if not token_value:
        raise AuthenticationFailed('A valid gallery access token is required.')
    try:
        token = AccessToken(token_value)
    except Exception as exc:
        raise AuthenticationFailed('Invalid or expired gallery access token.') from exc
    if token.get('token_scope') != 'gallery_access' or str(token.get('gallery_id')) != str(gallery.id):
        raise PermissionDenied('This token is not valid for the requested gallery.')
    return token


class PublicGalleryVerifyPinView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_identifier):
        gallery = get_object_or_404(Gallery, public_identifier=public_identifier, published=True)
        pin = request.data.get('pin')

        key = gallery_pin_attempt_key(request, public_identifier)
        attempts = cache.get(key, 0)
        if attempts >= 5:
            raise Throttled(detail='Too many incorrect PIN attempts. Please try again later.')

        if not isinstance(pin, str) or not check_password(
            pin,
            gallery.pin_hash,
        ):
            handle_failed_pin_attempt(request, public_identifier)
            raise AuthenticationFailed('Invalid gallery PIN.')

        cache.delete(key)

        token = AccessToken()
        token['gallery_id'] = str(gallery.id)
        token['token_scope'] = 'gallery_access'
        token.set_exp(lifetime=timedelta(minutes=15))

        return success_response(
            {
                'gallery_access_token': str(token),
                'expires_in': 900,
            }
        )

class PublicGalleryDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_identifier):
        gallery = published_gallery(public_identifier)
        gallery_token(request, gallery)
        return success_response({
            'public_identifier': gallery.public_identifier,
            'published_at': gallery.published_at,
            'photos': PublicPhotoSerializer(gallery.gallery_photos.all(), many=True).data,
        })


class PublicGalleryPhotoUrlView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_identifier, photo_id):
        gallery = published_gallery(public_identifier)
        gallery_token(request, gallery)
        selection = gallery.gallery_photos.select_related('photo').filter(photo_id=photo_id).first()
        if selection is None or selection.photo is None:
            raise PermissionDenied('This photo is not available in the published gallery.')
        try:
            url = create_download_url(selection.photo.storage_key)
        except Exception as exc:
            raise StorageUnavailable() from exc
        return success_response({'url': url, 'expires_in': 300})