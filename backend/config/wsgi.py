import os
import time
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("TZ", "America/El_Salvador")
try:
    time.tzset()
except AttributeError:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
