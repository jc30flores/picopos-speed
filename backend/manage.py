#!/usr/bin/env python
import os
import sys
import time


os.environ.setdefault("TZ", "America/El_Salvador")
try:
    time.tzset()
except AttributeError:
    pass


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if len(sys.argv) >= 2 and sys.argv[1] == "runserver":
        if len(sys.argv) == 2:
            sys.argv.append("0.0.0.0:8102")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
