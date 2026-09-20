from django.urls import path

from .public_views import PublicGalleryDetailView, PublicGalleryPhotoUrlView, PublicGalleryVerifyPinView

urlpatterns = [
    path('<str:public_identifier>/verify-pin/', PublicGalleryVerifyPinView.as_view(), name='public-gallery-verify-pin'),
    path('<str:public_identifier>/', PublicGalleryDetailView.as_view(), name='public-gallery-detail'),
    path('<str:public_identifier>/photos/<uuid:photo_id>/url/', PublicGalleryPhotoUrlView.as_view(), name='public-gallery-photo-url'),
]