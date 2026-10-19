"""Kipimo cha uhai kwa UptimeRobot na Render: mfumo uko hai na database inajibu."""
from django.db import connection
from django.http import HttpResponse


def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("database haipatikani", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
