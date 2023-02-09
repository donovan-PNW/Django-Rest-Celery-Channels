import shlex
import sys
import subprocess

from django.core.management.base import BaseCommand
from django.utils import autoreload


def restart_celery():
    '''
    meant to automatically reload celery worker whenever a change to code is made,
    as seen with manage.py runserver.
    must be run with "python manage.py celery_auto" to work
    '''
    runcmd = 'celery -A drf_cc worker -l INFO -E -P gevent'
    killcmd = f'pkill -f "{runcmd}"'
    # if sys.platform == 'win32':
    #     cmd = 'taskkill /f /t /im celery.exe'

    subprocess.call(shlex.split(killcmd))
    try:
        subprocess.call(shlex.split('redis-cli FLUSHALL'))
    except Exception as e:
        print(f'could not flush redis: {e}')
    subprocess.call(shlex.split(runcmd))


class Command(BaseCommand):

    def handle(self, *args, **options):
        print('Starting celery worker with autoreload...')
        autoreload.run_with_reloader(restart_celery)
