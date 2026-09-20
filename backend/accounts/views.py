from django.db import IntegrityError, transaction
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.permissions import IsAdmin
from core.responses import success_response

from .serializers import (
    AdminRegistrationSerializer,
    LoginRequestSerializer,
    TeamMemberCreateSerializer,
    UserSerializer,
)
from .models import User


class RegisterAdminView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.ALLOW_PUBLIC_ADMIN_REGISTRATION:
            raise NotFound()
        if request.data.get('email') and User.objects.filter(email__iexact=request.data['email']).exists():
            return success_response({'code': 'conflict', 'message': 'An account with this email already exists.'}, status.HTTP_409_CONFLICT)
        serializer = AdminRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            return success_response({'code': 'conflict', 'message': 'An account with this email already exists.'}, status.HTTP_409_CONFLICT)
        return success_response(UserSerializer(user).data, status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return success_response(response.data, response.status_code)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return success_response(
                {'code': 'validation_error', 'message': 'A refresh token is required.'},
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return success_response(
                {'code': 'invalid_token', 'message': 'The refresh token is invalid or expired.'},
                status.HTTP_400_BAD_REQUEST,
            )
        return success_response({'message': 'Logged out.'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(UserSerializer(request.user).data)


class RegisterTeamMemberView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        if request.data.get('email') and User.objects.filter(email__iexact=request.data['email']).exists():
            return success_response({'code': 'conflict', 'message': 'An account with this email already exists.'}, status.HTTP_409_CONFLICT)
        serializer = TeamMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            return success_response({'code': 'conflict', 'message': 'An account with this email already exists.'}, status.HTTP_409_CONFLICT)
        return success_response(UserSerializer(user).data, status.HTTP_201_CREATED)