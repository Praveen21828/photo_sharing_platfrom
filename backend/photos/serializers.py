import os

from rest_framework import serializers

from .models import Photo

ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}


class PhotoSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.UUIDField(source='uploaded_by_id', read_only=True)
    event = serializers.UUIDField(source='event_id', read_only=True)

    class Meta:
        model = Photo
        fields = ['id', 'event', 'uploaded_by', 'filename', 'file_size', 'created_at']
        read_only_fields = fields


class PhotoUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1, max_value=10 * 1024 * 1024)
    content_type = serializers.CharField(required=True, allow_blank=False)

    def validate_filename(self, value):
        filename = value.replace('\\', '/').split('/')[-1].strip()
        if not filename or filename in {'.', '..'}:
            raise serializers.ValidationError('A valid filename is required.')
        if any(part in {'', '.', '..'} for part in filename.split('/')):
            raise serializers.ValidationError('Invalid filename path.')
        return filename

    def validate_content_type(self, value):
        normalized = str(value).strip().lower()
        if normalized not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError('Only JPEG, PNG, and WebP image uploads are allowed.')
        return normalized

    def validate(self, attrs):
        filename = attrs.get('filename', '')
        content_type = attrs.get('content_type')
        extension = os.path.splitext(filename)[1].lower()
        expected_exts = {'.jpg', '.jpeg', '.png', '.webp'}

        if extension and extension not in expected_exts:
            raise serializers.ValidationError({'filename': 'The filename extension is not allowed for image uploads.'})

        if content_type == 'image/jpeg' and extension not in {'.jpg', '.jpeg'}:
            raise serializers.ValidationError({'content_type': 'The image MIME type does not match the filename.'})
        if content_type == 'image/png' and extension != '.png':
            raise serializers.ValidationError({'content_type': 'The image MIME type does not match the filename.'})
        if content_type == 'image/webp' and extension != '.webp':
            raise serializers.ValidationError({'content_type': 'The image MIME type does not match the filename.'})

        return attrs