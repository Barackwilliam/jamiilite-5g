import random
from urllib.parse import parse_qsl

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core import events
from core.models import Router

from . import localsync, routeros

# Router zinaripoti kila sekunde chache, kwa hiyo kusafisha matukio ya zamani ya
# ramani ya Live kunafanyika mara chache tu (njia ya local haina RADIUS server ya kufanya hivyo).
PRUNE_CHANCE = 0.002


def _script_response(text):
    return HttpResponse(text, content_type="text/plain; charset=utf-8")


def _active_router(token):
    return get_object_or_404(Router, provision_token=token, is_active=True)


@require_GET
def setup_script(request, token):
    return _script_response(routeros.setup_script(_active_router(token)))


@csrf_exempt  # Inaitwa na router, si browser; token ndiyo uthibitisho.
@require_POST
def checkin(request, token):
    report = dict(parse_qsl(request.body.decode("utf-8", errors="replace")))
    try:
        active_clients = max(0, int(report.get("users", 0)))
    except ValueError:
        active_clients = 0

    with transaction.atomic():
        router = get_object_or_404(
            Router.objects.select_for_update(), provision_token=token, is_active=True
        )
        router.last_seen_at = timezone.now()
        router.routeros_version = report.get("v", "")[:60]
        router.uptime = report.get("up", "")[:40]
        router.active_clients = active_clients
        router.save(
            update_fields=["last_seen_at", "routeros_version", "uptime", "active_clients"]
        )

        pending = list(router.commands.filter(delivered_at__isnull=True).select_related("router"))
        if pending:
            router.commands.filter(pk__in=[c.pk for c in pending]).update(
                delivered_at=timezone.now()
            )
            for command in pending:
                events.record(router, events.Kind.COMMAND, detail=command.get_action_display())

        sync = localsync.handle_report(router, report) if settings.JAMIILITE_AUTH_MODE == "local" else []

    if random.random() < PRUNE_CHANCE:
        events.prune()
    return _script_response(routeros.command_script(pending, sync))
