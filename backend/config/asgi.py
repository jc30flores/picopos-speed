import os
import time
from django.core.asgi import get_asgi_application

os.environ.setdefault("TZ", "America/El_Salvador")
try:
    time.tzset()
except AttributeError:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
