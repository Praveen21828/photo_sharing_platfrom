from django.urls import reverse
from rest_framework import serializers

from photos.serializers import PhotoSerializer

from .models import Gallery, GalleryPhoto


class GalleryPhotoSerializer(serializers.ModelSerializer):
    photo = PhotoSerializer(read_only=True)
    photo_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = GalleryPhoto
        fields = ['id', 'photo', 'photo_id', 'created_at']
        read_only_fields = ['id', 'photo', 'created_at']


class PublicPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GalleryPhoto
        fields = ['id', 'created_at']

    def to_representation(self, instance):
        return {
            'id': instance.photo_id,
            'filename': instance.photo.filename,
            'file_size': instance.photo.file_size,
            'created_at': instance.photo.created_at,
        }


class GallerySerializer(serializers.ModelSerializer):
    gallery_photos = GalleryPhotoSerializer(many=True, read_only=True)
    pin = serializers.CharField(write_only=True, required=False, min_length=4, max_length=32)
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = Gallery
        fields = ['id', 'event', 'public_identifier', 'published', 'created_at', 'published_at', 'gallery_photos', 'pin', 'share_url']
        read_only_fields = ['id', 'event', 'public_identifier', 'published', 'created_at', 'published_at', 'gallery_photos', 'share_url']

    def get_share_url(self, obj):
        request = self.context.get('request')
        if request is None:
            return f'/public/galleries/{obj.public_identifier}/'
        return request.build_absolute_uri(reverse('public-gallery-detail', kwargs={'public_identifier': obj.public_identifier}))
