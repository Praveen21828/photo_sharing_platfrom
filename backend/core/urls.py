from django.urls import include, path
from .views import health_check

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('auth/', include('accounts.urls')),
    path('events/', include('events.urls')),
    path('photos/', include('photos.urls')),
    path('galleries/', include('galleries.urls')),
    path('public/galleries/', include('galleries.public_urls')),
]
