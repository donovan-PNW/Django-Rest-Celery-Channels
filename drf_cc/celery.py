import os
from django.conf import settings

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'drf_cc.settings')

# explicitly select redis as our message broker, there are also other options
if settings.TESTING or settings.DEBUG:
    app = Celery('drf_cc', broker='redis://localhost', backend='redis://localhost')
else:
    app = Celery('drf_cc', broker='redis://redis', backend='redis://redis')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# namespace='CELERY' means all celery-related configuration keys
# should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
