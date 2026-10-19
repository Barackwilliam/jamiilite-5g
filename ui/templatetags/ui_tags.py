from django import template
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Ikoni za mstari (24x24, stroke). Zinarithi rangi ya maandishi (currentColor).
ICONS = {
    "home": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>',
    "router": '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 13V9m10 4V9"/><path d="M7 16.5h.01M11 16.5h.01"/>',
    "package": '<path d="M12 3 4 7v10l8 4 8-4V7z"/><path d="m4 7 8 4 8-4M12 11v10"/>',
    "ticket": '<path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/><path d="M14 5v12" stroke-dasharray="2 2"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "wallet": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><path d="M16 14.5h2"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2.1-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2.1 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12a7 7 0 0 0 .1 1.2l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2.1 1.2L10 21h4l.5-2.6a7 7 0 0 0 2.1-1.2l2.3.9 2-3.4-2-1.5A7 7 0 0 0 19 12z"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18.5 20a6.5 6.5 0 0 0-2.5-5.1"/>',
    "shield": '<path d="M12 3 5 6v5c0 4.5 3 8.4 7 10 4-1.6 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/>',
    "send": '<path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/>',
    "logout": '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "print": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16m0 4v-4h-4"/>',
    "power": '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0"/><path d="M5.5 12.5a10 10 0 0 1 13 0"/><path d="M9 16a5 5 0 0 1 6 0"/><path d="M12 19.5h.01"/>',
    "alert": '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17h.01"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
}


@register.simple_tag
def icon(name, size=20):
    paths = ICONS.get(name, "")
    return format_html(
        '<svg class="icon" width="{0}" height="{0}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{1}</svg>',
        size,
        mark_safe(paths),
    )


@register.filter
def tsh(value):
    try:
        return f"Tsh {int(value):,}"
    except (TypeError, ValueError):
        return "Tsh 0"


@register.filter
def signed_tsh(value):
    value = int(value or 0)
    return f"{'+' if value > 0 else '−' if value < 0 else ''}Tsh {abs(value):,}"


@register.filter
def ago(value):
    """Muda uliopita kwa Kiswahili, mfano 'dakika 3 zilizopita'."""
    if not value:
        return "bado"
    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return "sasa hivi"
    for size, one, many in ((86400, "siku", "siku"), (3600, "saa", "saa"), (60, "dakika", "dakika")):
        if seconds >= size:
            count = seconds // size
            return f"{one if count == 1 else many} {count} zilizopita"
    return "sasa hivi"


@register.filter
def phone_display(value):
    """255712345678 → 0712 345 678"""
    value = str(value or "")
    if len(value) == 12 and value.startswith("255"):
        local = "0" + value[3:]
        return f"{local[:4]} {local[4:7]} {local[7:]}"
    return value


@register.simple_tag(takes_context=True)
def page_url(context, number):
    """Link ya ukurasa mwingine bila kupoteza vichujio (q, hali...) vilivyopo."""
    query = context["request"].GET.copy()
    query["ukurasa"] = number
    return "?" + query.urlencode()
