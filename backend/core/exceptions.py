from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return Response({
            'code': 'server_error',
            'message': 'An unexpected server error occurred.',
            'details': {},
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(response.data, dict) and 'detail' in response.data:
        message = response.data['detail']
        details = {key: value for key, value in response.data.items() if key != 'detail'}
    else:
        message = 'Request validation failed.'
        details = response.data

    response.data = {
        'code': getattr(exc, 'default_code', 'api_error'),
        'message': str(message),
        'details': details,
    }
    return response
