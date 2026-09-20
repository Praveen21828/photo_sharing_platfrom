from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import IsAdmin
from core.responses import success_response
from events.models import Event

from .models import Gallery
from .serializers import GalleryPhotoSerializer, GallerySerializer
from .services import create_gallery, deselect_photo, publish_gallery, select_photo


def owned_galleries(user):
    return Gallery.objects.filter(event__created_by=user).prefetch_related('gallery_photos__photo')


class GalleryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, event_id):
        galleries = owned_galleries(request.user).filter(event_id=event_id)
        return success_response(GallerySerializer(galleries, many=True).data)

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id, created_by=request.user)
        serializer = GallerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pin = serializer.validated_data.get('pin')
        if not pin:
            return success_response({'code': 'validation_error', 'message': 'A PIN is required.'}, status.HTTP_400_BAD_REQUEST)
        gallery = create_gallery(event, pin)
        return success_response(GallerySerializer(gallery).data, status.HTTP_201_CREATED)


class GalleryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gallery_id):
        gallery = get_object_or_404(owned_galleries(request.user), id=gallery_id)
        return success_response(GallerySerializer(gallery).data)


class GalleryPhotoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, gallery_id):
        gallery = get_object_or_404(Gallery, id=gallery_id, event__created_by=request.user)
        serializer = GalleryPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            selection = select_photo(gallery, serializer.validated_data['photo_id'])
        except IntegrityError:
            return success_response(
                {'code': 'conflict', 'message': 'Photo is already selected for this gallery.'},
                status.HTTP_409_CONFLICT,
            )
        return success_response(GalleryPhotoSerializer(selection).data, status.HTTP_201_CREATED)


class GalleryPhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, gallery_id, photo_id):
        gallery = get_object_or_404(Gallery, id=gallery_id, event__created_by=request.user)
        try:
            deselect_photo(gallery, photo_id)
        except ValidationError:
            raise
        return success_response({'deleted': True, 'photo_id': str(photo_id)})


class GalleryPublishView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, gallery_id):
        gallery = get_object_or_404(Gallery, id=gallery_id, event__created_by=request.user)
        gallery = publish_gallery(gallery)
        return success_response(GallerySerializer(gallery).data)
