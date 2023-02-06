from . import consumers
from django.urls import include, re_path

websocket_urlpatterns = [
    re_path(r'^socket/', consumers.BulkUploadLearnerSocket.as_asgi(), name='general communication socket'),
]
