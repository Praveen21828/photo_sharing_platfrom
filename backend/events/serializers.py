from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Event, EventMember


class EventSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Event
        fields = ['id', 'name', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Event name is required.')
        return value.strip()


class EventMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = EventMember
        fields = ['id', 'user', 'user_id', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def validate_user_id(self, value):
        from accounts.models import User

        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError('Team Member was not found.')
        if user.role != User.Role.TEAM_MEMBER:
            raise serializers.ValidationError('Only Team Members can be assigned to events.')
        return value

    def create(self, validated_data):
        from accounts.models import User

        return EventMember.objects.create(
            event=self.context['event'],
            user=User.objects.get(id=validated_data['user_id']),
        )