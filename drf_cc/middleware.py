from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from channels.auth import AuthMiddleware
from channels.db import database_sync_to_async
from channels.sessions import CookieMiddleware, SessionMiddleware
from rest_framework.authtoken.models import Token

User = get_user_model()


# https://testdriven.io/courses/taxi-react/websockets-part-one/
@database_sync_to_async
def get_user(scope):
    close_old_connections()
    query_string = parse_qs(scope['query_string'].decode())
    token = query_string.get('token')[0]
    if not token:
        return AnonymousUser()
    try:
        access_token = Token.objects.get(key=token)
    except Token.DoesNotExist:
        return AnonymousUser()
    if not access_token.user.is_active:
        return AnonymousUser()
    return access_token.user


class TokenAuthMiddleware(AuthMiddleware):
    async def resolve_scope(self, scope):
        scope['user']._wrapped = await get_user(scope)


def TokenAuthMiddlewareStack(inner):
    return CookieMiddleware(SessionMiddleware(TokenAuthMiddleware(inner)))
