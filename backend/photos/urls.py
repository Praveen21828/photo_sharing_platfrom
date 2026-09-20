from django.urls import path

from .views import EventPhotoListCreateView, PhotoDetailView, PhotoDownloadUrlView, PhotoUploadCompleteView

urlpatterns = [
    path('events/<uuid:event_id>/', EventPhotoListCreateView.as_view(), name='event-photo-list-create'),
    path('<uuid:photo_id>/', PhotoDetailView.as_view(), name='photo-detail'),
    path('<uuid:photo_id>/upload-complete/', PhotoUploadCompleteView.as_view(), name='photo-upload-complete'),
    path('<uuid:photo_id>/download-url/', PhotoDownloadUrlView.as_view(), name='photo-download-url'),
]