"""
Sentry: inatuma email kila kosa likitokea kwenye production, pamoja na mahali hasa lilipotokea.
Inawashwa tu ikiwa SENTRY_DSN imewekwa.

Hakuna data binafsi inayotumwa: hakuna IP, cookies wala fomu (namba za simu, password),
na siri za routers kwenye anwani (/r/<siri>/...) zinafichwa.
"""

import re

ROUTER_TOKEN = re.compile(r"/r/[^/]+/")


def _hide_tokens(value):
    return ROUTER_TOKEN.sub("/r/[siri]/", value) if isinstance(value, str) else value


def before_send(event, hint):
    request = event.get("request") or {}
    for key in ("url", "query_string"):
        if key in request:
            request[key] = _hide_tokens(request[key])
    if "transaction" in event:
        event["transaction"] = _hide_tokens(event["transaction"])
    return event


def init(dsn, environment="production", release=None, traces_sample_rate=0.0):
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=traces_sample_rate,
        before_send=before_send,
    )
