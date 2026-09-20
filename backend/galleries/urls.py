from django.urls import path

from .views import GalleryDetailView, GalleryListCreateView, GalleryPhotoCreateView, GalleryPhotoDeleteView, GalleryPublishView

urlpatterns = [
    path('events/<uuid:event_id>/', GalleryListCreateView.as_view(), name='gallery-list-create'),
    path('<uuid:gallery_id>/', GalleryDetailView.as_view(), name='gallery-detail'),
    path('<uuid:gallery_id>/photos/', GalleryPhotoCreateView.as_view(), name='gallery-photo-create'),
    path('<uuid:gallery_id>/photos/<uuid:photo_id>/', GalleryPhotoDeleteView.as_view(), name='gallery-photo-delete'),
    path('<uuid:gallery_id>/publish/', GalleryPublishView.as_view(), name='gallery-publish'),
]