from django.conf import settings
import redis
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from hashlib import sha1

REDIS_CLIENT = redis.Redis(host=settings.REDIS_HOST)


class BulkUploadLearnerSocket(AsyncJsonWebsocketConsumer):
    '''
    Websocket consumers are analogous to django views. This one is invoked in
    in vanroboapp/api/routing.py (which is analogous to urls.py), within websocket_urlpatterns,
    which is, in turn, invoked in asgi.py. Similar to a view's builtin functions (of get, post etc)
    a consumer's behavior can be defined within connect/receive/disconnect functions
    as well as with other functions for custom messages
    '''

    async def connect(self):
        """
        Handle a new websocket connection, check for a valid token before doing so.
        Check celery availability (and any running tasks) and provide details to frontend.
        auth is handled by middleware and token is passed through query parameter
        eg example.com/socket/?token=blahblahblah

        NOTE: redis lock is dependent on the group's name, as well as the name
        of the celery task that we are calling. In this case, organization 99's
        lock name will be 'process_bulk_upload_99'. We opaquely check this lock with tasks.py's
        'single_operation' decorator, which in turn checks the calling function's name
        (in this case, process_bulk_upload(...)) and combines it with an org ID
        to create or release a lock.
        """
        self.group_name = "default_group"

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        await self.send_json({"type": "websocket.accept"})
        await self.send_json({"type": "websocket.send", "msg": "connection successful"})
        await self.send_json({
            "type": "websocket.send",
            "event_type": "celery_status",
            "content": "GREEN",
        })

    async def receive(self, text_data=None, bytes_data=None):
        # demo function, simply hash and return a string
        print("receive", text_data, bytes_data)
        hashed = sha1(text_data.encode('utf-8')).hexdigest()
        await self.send_json({
            "type": "websocket.send",
            "msg": {f"'{text_data}' to sha1": hashed}
        })

    async def disconnect(self, event):
        print("disconnected", event)
        # Leave room group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
