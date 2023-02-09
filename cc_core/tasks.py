from django.conf import settings
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from celery.utils.log import get_task_logger
from celery import states
from celery.exceptions import Ignore
import redis
import time
import functools
from datetime import datetime

logger = get_task_logger(__name__)

channel_layer = get_channel_layer()


if settings.TESTING:
    from redislite import Redis
    REDIS_CLIENT = Redis(settings.REDISLITE_FILE)
else:
    REDIS_CLIENT = redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
    )


# class socket_interface:
#
#     def __init__(self, org=None, task_user_id=None, group_name=None):
#         self.channel_layer = get_channel_layer()
#         self.org = org
#         self.task_user_id = task_user_id
#         self.group_name = group_name
#
#     def send_message(self, evt_type, content):
#         async_to_sync(self.channel_layer.group_send)(self.group_name, {
#             "type": "relay.msg",
#             "event_type": evt_type,
#             "content": content,
#         })
#
#     def log_interaction(self, **kwargs):
#         receipt_serializer = serializers.FileUploadReceiptSerializer(
#             # base model handles timestamp and user
#             data={**kwargs},
#         )
#         if receipt_serializer.is_valid():
#             receipt_serializer.save()

def log_interaction(**kwargs):
    pass


def single_operation(timeout=None):
    """
    Decorator to ensure only one celery task gets invoked at a time.
    https://betterprogramming.pub/python-celery-best-practices-ae182730bb81
    takes function name and 'org' kwarg to create a key
    NEEDS ORG to lock a single organization, otherwise it will lock task for all users
    """
    def _dec(run_func):
        @functools.wraps(run_func)
        def _caller(*args, **kwargs):
            try:
                key = f"{run_func.__name__}_{kwargs['hash_key']}"
            except KeyError:
                # locks function for all anonymous users, probably want to change this later
                key = f"{run_func.__name__}"
            func_result = None
            have_lock = False
            lock = REDIS_CLIENT.lock(key, timeout=timeout)
            try:
                have_lock = lock.acquire(blocking=False)
                if have_lock:
                    func_result = run_func(*args, **kwargs)
            finally:
                if have_lock:
                    lock.release()
            if func_result:
                return func_result
        return _caller
    return _dec


# run with 'celery -A drf_cc worker -l INFO -E -P gevent' in production
# or 'python manage.py celery_auto' (in a separate terminal window) in development
# (see cc_core/management/commands/celery_auto.py)
@shared_task(bind=True)
@single_operation(60 * 10)
def get_zen(self, hash_key=None):
    '''
    simple demo task
    '''
    try:
        group_name = "default_group"
        # group_name = f"{hash_key}"

        zen = ''' The Zen of Python, by Tim Peters
            Beautiful is better than ugly.
            Explicit is better than implicit.
            Simple is better than complex.
            Complex is better than complicated.
            Flat is better than nested.
            Sparse is better than dense.
            Readability counts.
            Special cases aren't special enough to break the rules.
            Although practicality beats purity.
            Errors should never pass silently.
            Unless explicitly silenced.
            In the face of ambiguity, refuse the temptation to guess.
            There should be one-- and preferably only one --obvious way to do it.
            Although that way may not be obvious at first unless you're Dutch.
            Now is better than never.
            Although never is often better than *right* now.
            If the implementation is hard to explain, it's a bad idea.
            If the implementation is easy to explain, it may be a good idea.
            Namespaces are one honking great idea -- let's do more of those! '''

        zenlist = zen.split(sep='\n')
        for line in zenlist:
            line = " ".join(line.split())
            async_to_sync(channel_layer.group_send)(group_name, {
                "type": "relay.msg",
                "event_type": "zen_msg",
                "content": line
            })
            time.sleep(1)

        current_time = datetime.now()
        receipt_data = {
            'hash_key': hash_key,
            'output': current_time
        }
        log_interaction(**receipt_data)
        logger.info(f"Output: get_zen completed at {current_time}")

    except Exception as e:
        logger.exception(f'celery task get_zen failed: {hash_key}')
        error_dict = e.args[0]

        async_to_sync(channel_layer.group_send)(group_name, {
            "type": "relay.msg",
            "event_type": "failed_task",
            "content": error_dict,
        })
        self.update_state(
            state=states.FAILURE,
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)[1:-1],  # traceback.format_exc().split('\n'),
            }
        )
        receipt_data = {
            'hash_key': hash_key,
            'exception': e,
        }
        log_interaction(**receipt_data)
        # ignore simply stops celery from overwriting the failure state when the overall task 'succeeds'
        raise Ignore()
        return
