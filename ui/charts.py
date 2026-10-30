"""
Chati ndogo za mauzo zinazochorwa kama SVG upande wa server.

Hakuna maktaba ya nje: SVG inatengenezwa hapa, na ui/static/ui/app.js
inaongeza tooltip ya kila bar. Jedwali la thamani zote linaambatana na kila
chati, ili tooltip isiwe njia pekee ya kusoma namba.
"""

import math
from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import dateformat, timezone


# Vipimo vya viewBox; SVG inapanuka kufuata upana wa kadi.
# Upana mkubwa: kwenye kompyuta chati haiwi ndefu kupita kiasi, na maandishi yanabaki madogo.
WIDTH, HEIGHT = 900, 240
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 44, 8, 12, 28
MAX_BAR = 24
RADIUS = 4


def day_abbr(day):
    """Jina fupi la siku kwa lugha inayotumika (mfano "Jtatu" / "Mon")."""
    # Tafsiri ya Django ya Kiswahili ina "jtano" kwa herufi ndogo; zote zianze kwa herufi kubwa.
    name = dateformat.format(day, "D")
    return name[:1].upper() + name[1:]


def daily_totals(queryset, date_field, value_field, days=14, now=None):
    """[(tarehe, jumla)] kwa siku `days` zilizopita, siku zisizo na kitu zikiwa 0."""
    tz = timezone.get_current_timezone()
    today = timezone.localtime(now or timezone.now(), tz).date()
    start = today - timedelta(days=days - 1)
    rows = (
        queryset.filter(**{f"{date_field}__date__gte": start})
        .annotate(day=TruncDate(date_field, tzinfo=tz))
        .values("day")
        .annotate(total=Sum(value_field))
    )
    by_day = {row["day"]: row["total"] or 0 for row in rows}
    return [(start + timedelta(days=i), by_day.get(start + timedelta(days=i), 0)) for i in range(days)]


def nice_ceiling(value):
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


def compact(value):
    if value >= 1_000_000:
        text, unit = f"{value / 1_000_000:.1f}", "M"
    elif value >= 1_000:
        text, unit = f"{value / 1_000:.1f}", "K"
    else:
        return f"{value:g}"
    return text.removesuffix(".0") + unit


def _column_path(x, y, width, height):
    """Bar yenye pembe za juu za mviringo (4px) na msingi ulionyooka."""
    r = min(RADIUS, width / 2, height)
    bottom = y + height
    return (
        f"M{x:.1f},{bottom:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + width - r:.1f} Q{x + width:.1f},{y:.1f} {x + width:.1f},{y + r:.1f} "
        f"V{bottom:.1f} Z"
    )


def bar_chart(points, unit="Tsh"):
    """Geuza [(tarehe, thamani)] kuwa vipimo vya SVG kwa template ya ui/_bar_chart.html."""
    peak = max((value for _, value in points), default=0)
    top = nice_ceiling(peak)
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    slot = plot_w / max(len(points), 1)
    bar_w = min(MAX_BAR, slot * 0.6)
    baseline = PAD_TOP + plot_h

    # Lebo za tarehe chache tu (mwanzo, katikati, mwisho), zisisongamane.
    label_every = max(1, math.ceil(len(points) / 7))
    bars = []
    peak_marked = False
    for i, (day, value) in enumerate(points):
        is_peak = value == peak and peak > 0 and not peak_marked
        peak_marked = peak_marked or is_peak
        height = 0 if top == 0 else plot_h * value / top
        x = PAD_LEFT + slot * i + (slot - bar_w) / 2
        bars.append(
            {
                "path": _column_path(x, baseline - height, bar_w, height) if value > 0 else "",
                "hit_x": round(PAD_LEFT + slot * i, 1),
                "hit_w": round(slot, 1),
                "label_x": round(x + bar_w / 2, 1),
                "top_y": round(baseline - height - 6, 1),
                "peak_label": compact(value),
                "show_label": (len(points) - 1 - i) % label_every == 0,
                "day_label": f"{day_abbr(day)} {day.day}",
                "date": day,
                "value": value,
                "value_display": f"{unit} {value:,}",
                "is_peak": is_peak,
            }
        )

    ticks = [
        {"y": round(baseline - plot_h * fraction, 1), "label": compact(top * fraction)}
        for fraction in (0, 0.5, 1)
    ]
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "plot_left": PAD_LEFT,
        "plot_right": WIDTH - PAD_RIGHT,
        "baseline": baseline,
        "label_y": baseline + 18,
        "plot_top": PAD_TOP,
        "plot_h": plot_h,
        "bars": bars,
        "ticks": ticks,
        "total": sum(value for _, value in points),
        "total_display": f"{unit} {sum(value for _, value in points):,}",
        "is_empty": peak == 0,
    }
