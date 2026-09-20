from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        database_status = 'ok'
    except Exception:
        database_status = 'unavailable'

    status_code = 200 if database_status == 'ok' else 503
    return Response({
        'status': 'ok' if status_code == 200 else 'degraded',
        'service': 'photo-sharing-api',
        'database': database_status,
    }, status=status_code)
