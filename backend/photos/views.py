import os

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import PhotoPagination
from core.responses import success_response
from events.models import Event

from .models import Photo
from .serializers import PhotoSerializer, PhotoUploadSerializer
from .services import (
    build_storage_key,
    create_download_url,
    create_upload_url,
    delete_uploaded_object,
    verify_uploaded_object,
)


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = 'Object storage is not configured or unavailable.'
    default_code = 'storage_unavailable'


def visible_events(user):
    if user.role == user.Role.ADMIN:
        return Event.objects.filter(created_by=user)
    return Event.objects.filter(memberships__user=user)


def visible_photos(user):
    if user.role == user.Role.ADMIN:
        return Photo.objects.filter(event__created_by=user)
    return Photo.objects.filter(
        event__memberships__user=user,
        uploaded_by=user,
    ).distinct()


class EventPhotoListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PhotoPagination

    def get_event(self, request, event_id):
        return get_object_or_404(visible_events(request.user), id=event_id)

    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(event.photos.select_related('uploaded_by'), request, view=self)
        return paginator.get_paginated_response(PhotoSerializer(page, many=True).data)

    def post(self, request, event_id):
        event = self.get_event(request, event_id)
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        storage_key = build_storage_key(event.id, serializer.validated_data['filename'])
        photo = None
        try:
            with transaction.atomic():
                photo = Photo.objects.create(
                    event=event,
                    uploaded_by=request.user,
                    storage_key=storage_key,
                    filename=serializer.validated_data['filename'],
                    file_size=serializer.validated_data['file_size'],
                )
                upload_url = create_upload_url(
                    storage_key,
                    photo.file_size,
                    serializer.validated_data['content_type'],
                )
        except APIException:
            raise
        except Exception as exc:
            if photo is not None:
                try:
                    delete_uploaded_object(storage_key)
                except Exception:
                    pass
            raise StorageUnavailable() from exc
        return success_response({
            'photo': PhotoSerializer(photo).data,
            'upload_url': upload_url,
            'expires_in': 600,
        }, status.HTTP_201_CREATED)


class PhotoDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, photo_id):
        photo = get_object_or_404(visible_photos(request.user), id=photo_id)
        return success_response(PhotoSerializer(photo).data)


class PhotoDownloadUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, photo_id):
        photo = get_object_or_404(visible_photos(request.user), id=photo_id)
        try:
            url = create_download_url(photo.storage_key)
        except Exception as exc:
            raise StorageUnavailable() from exc
        return success_response({'url': url, 'expires_in': 300})


class PhotoUploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, photo_id):
        photo = get_object_or_404(visible_photos(request.user), id=photo_id)
        if photo.uploaded_by_id != request.user.id and request.user.role != request.user.Role.ADMIN:
            self.permission_denied(request, message='Only the uploader or an Admin/Lead can complete this upload.')
        try:
            expected_content_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
            }.get(os.path.splitext(photo.filename)[1].lower())
            verify_uploaded_object(photo.storage_key, photo.file_size, expected_content_type)
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(exc)) from exc
        except Exception as exc:
            raise StorageUnavailable() from exc
        return success_response({'photo': PhotoSerializer(photo).data, 'status': 'ready'})