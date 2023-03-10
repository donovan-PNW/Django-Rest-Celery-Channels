from django.conf import settings
import redis
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from hashlib import sha1
from cc_core.tasks import get_zen

REDIS_CLIENT = redis.Redis(host=settings.REDIS_HOST)


class BulkUploadLearnerSocket(AsyncJsonWebsocketConsumer):
    '''
    Websocket consumers are analogous to django views. This one is invoked in
    in cc_core/routing.py (which is analogous to urls.py), within websocket_urlpatterns,
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
        lock name will be 'get_zen_99'. We opaquely check this lock with tasks.py's
        'single_operation' decorator, which in turn checks the calling function's name
        (in this case, get_zen(...)) and combines it with an org ID
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

    async def relay_msg(self, event):
        # Triggered by celery worker when it sends 'relay.msg' event to this channel
        # simply takes the message contents and sends it to the frontend using websockets
        await self.send_json({
            "type": "websocket.send",
            "event_type": event['event_type'],
            "content": event['content'],
        })

    async def receive(self, text_data=None, bytes_data=None):
        print("receive", text_data, bytes_data)
        # demo function, simply hash and return a string
        hashed = sha1(text_data.encode('utf-8')).hexdigest()
        await self.send_json({
            "type": "websocket.send",
            "msg": {f"'{text_data}' to sha1": hashed}
        })
        # then, run a celery function, which will run for a few seconds
        # and send updates to the client directly via relay_msg()
        get_zen.apply_async(kwargs={'hash_key': hashed})

    async def disconnect(self, event):
        print("disconnected", event)
        # Leave room group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
