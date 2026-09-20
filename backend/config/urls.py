from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.defaults import page_not_found


def api_not_found(request, exception=None, template_name='404.html'):
    if request.path.startswith('/api/'):
        return JsonResponse({
            'code': 'not_found',
            'message': 'The requested resource was not found.',
            'details': {},
        }, status=404)
    return page_not_found(request, exception, template_name)


handler404 = api_not_found

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
]
