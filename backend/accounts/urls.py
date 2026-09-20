from django.urls import path

from .views import LoginView, LogoutView, MeView, RegisterAdminView, RegisterTeamMemberView, RefreshView

urlpatterns = [
    path('register/', RegisterAdminView.as_view(), name='register-admin'),
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='current-user'),
    path('team-members/', RegisterTeamMemberView.as_view(), name='register-team-member'),
]