"""PDF ya vocha (A4, safu 3, vocha 21 kwa ukurasa), muundo sawa na ukurasa wa kuchapisha."""
import io
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils.translation import gettext as _
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

FONTS = Path(__file__).resolve().parent / "fonts"
NAVY, BLUE, BLUE_2, BLUE_3 = HexColor("#0a2245"), HexColor("#1557d6"), HexColor("#2d7cf6"), HexColor("#0b47c9")
CODE_BG, BORDER, TEXT, MUTED = HexColor("#0b3388"), HexColor("#9fb5dd"), HexColor("#3b4a66"), HexColor("#8a97b0")
GREEN, RED = HexColor("#18a957"), HexColor("#c43d2f")

MARGIN, GAP, COLS = 8 * mm, 3 * mm, 3
CARD_H = 33 * mm
PAD = 2.5 * mm

# Mawimbi ya pembeni (viewBox 120x60, y kuelekea chini), sawa na SVG ya ukurasa.
WAVE_BACK = [("M", 30, 0), ("L", 120, 0), ("L", 120, 60), ("C", 98, 34, 70, 50, 52, 30), ("C", 40, 16, 44, 6, 30, 0)]
WAVE_FRONT = [("M", 58, 0), ("L", 120, 0), ("L", 120, 34), ("C", 104, 18, 86, 26, 74, 14), ("C", 68, 8, 66, 3, 58, 0)]

_registered = False


def _register_fonts():
    global _registered
    if _registered:
        return
    for name in ("inter-400", "inter-600", "sora-800"):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / f"{name}.ttf")))
    pdfmetrics.registerFontFamily("inter", normal="inter-400", bold="inter-600", italic="inter-400", boldItalic="inter-600")
    _registered = True


def _fit(text, font, size, width):
    """Kata maandishi yasizidi upana, ukiweka … mwishoni."""
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


def _wave(c, points, left, top, width, height, color):
    sx, sy = width / 120, height / 60
    to = lambda px, py: (left + px * sx, top - py * sy)  # noqa: E731
    path = c.beginPath()
    for op, *v in points:
        if op == "M":
            path.moveTo(*to(*v))
        elif op == "L":
            path.lineTo(*to(*v))
        else:
            path.curveTo(*to(v[0], v[1]), *to(v[2], v[3]), *to(v[4], v[5]))
    path.close()
    c.setFillColor(color)
    c.drawPath(path, stroke=0, fill=1)


def _wifi(c, cx, cy, size, color, width):
    """Alama ya WiFi: nukta na mistari mitatu ya mzunguko."""
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.setLineCap(1)
    c.circle(cx, cy, size * 0.09, stroke=0, fill=1)
    for r in (0.38, 0.66, 0.94):
        rad = size * r
        c.arc(cx - rad, cy - rad, cx + rad, cy + rad, 45, 90)


def _clock(c, cx, cy, r, color):
    c.setStrokeColor(color)
    c.setLineWidth(0.45)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.line(cx, cy, cx, cy + r * 0.6)
    c.line(cx, cy, cx + r * 0.45, cy - r * 0.25)


def _logo(owner):
    if not owner.logo:
        return None
    try:
        with owner.logo.open("rb") as fh:
            return ImageReader(io.BytesIO(fh.read()))
    except Exception:  # Logo isiposomeka, alama ya WiFi inatumika badala yake.
        return None


def _card(c, x, y, w, voucher, owner, logo, site_host, step_style):
    top = y + CARD_H
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(x, y, w, CARD_H, 3 * mm)
    c.clipPath(clip, stroke=0, fill=0)
    c.setFillColor(white)
    c.rect(x, y, w, CARD_H, stroke=0, fill=1)
    wave_w = w * 0.34
    _wave(c, WAVE_BACK, x + w - wave_w, top, wave_w, 8 * mm, BLUE_2)
    _wave(c, WAVE_FRONT, x + w - wave_w, top, wave_w, 8 * mm, BLUE_3)
    c.restoreState()
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, CARD_H, 3 * mm, stroke=1, fill=0)

    # Kichwa: alama, jina la biashara, kifurushi na bei
    r = 3.25 * mm
    cx, cy = x + PAD + r, top - PAD - r
    if logo:
        c.saveState()
        circle = c.beginPath()
        circle.circle(cx, cy, r)
        c.clipPath(circle, stroke=0, fill=0)
        c.drawImage(logo, cx - r, cy - r, 2 * r, 2 * r, preserveAspectRatio=True, anchor="c", mask="auto")
        c.restoreState()
    else:
        c.setFillColor(BLUE)
        c.circle(cx, cy, r, stroke=0, fill=1)
        _wifi(c, cx, cy - 1.1 * mm, 2.3 * mm, white, 0.7)
    text_x = cx + r + 2 * mm
    text_w = w * 0.66 - (text_x - x)
    c.setFillColor(NAVY)
    c.setFont("sora-800", 9)
    c.drawString(text_x, top - PAD - 3.2 * mm, _fit(owner.business_name, "sora-800", 9, text_w))
    _clock(c, text_x + 1.1 * mm, top - PAD - 6.15 * mm, 1.05 * mm, BLUE)
    c.setFillColor(BLUE)
    c.setFont("inter-600", 7.5)
    package = f"{voucher.package.name} · Tsh {voucher.package.price:,}"
    c.drawString(text_x + 3 * mm, top - PAD - 6.95 * mm, _fit(package, "inter-600", 7.5, text_w - 3 * mm))

    # Msimbo kwenye upau wa bluu iliyokolea
    bar_h, bar_y = 6 * mm, top - PAD - 7 * mm - 1.6 * mm - 6 * mm
    c.setFillColor(CODE_BG)
    c.roundRect(x + PAD, bar_y, w - 2 * PAD, bar_h, 2 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    code_font, code_size, spacing = "Courier-Bold", 12, 2.2
    code_w = pdfmetrics.stringWidth(voucher.code, code_font, code_size) + spacing * (len(voucher.code) - 1)
    c.saveState()  # nafasi kati ya herufi ni kwa msimbo peke yake
    text = c.beginText(x + (w - code_w) / 2, bar_y + 1.85 * mm)
    text.setFont(code_font, code_size)
    text.setCharSpace(spacing)
    text.textOut(voucher.code)
    c.drawText(text)
    c.restoreState()

    # Hatua mbili zenye namba
    wifi_name = escape(voucher.router.wifi_name or voucher.router.name)
    steps = [
        _("Washa WiFi kwenye simu au kifaa chako, kisha chagua <b>%(wifi)s</b>.") % {"wifi": wifi_name},
        _("Ingiza msimbo huu, kisha bonyeza <b>Unganisha</b>."),
    ]
    step_top = bar_y - 1.3 * mm
    side_w = 17 * mm
    for i, step in enumerate(steps):
        para = Paragraph(step.replace("<b>", '<b><font color="#0a2245">').replace("</b>", "</font></b>"), step_style)
        avail = w - 2 * PAD - 3.6 * mm - (side_w if i == len(steps) - 1 else 0)
        height = para.wrap(avail, 20 * mm)[1]
        para.drawOn(c, x + PAD + 3.6 * mm, step_top - height)
        c.setFillColor(BLUE)
        c.circle(x + PAD + 1.2 * mm, step_top - 1.3 * mm, 1.2 * mm, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("inter-600", 5.2)
        c.drawCentredString(x + PAD + 1.2 * mm, step_top - 1.95 * mm, str(i + 1))
        step_top -= height + 0.4 * mm

    # Alama ya WiFi ya kijani na anwani ya tovuti
    _wifi(c, x + w - PAD - 1.9 * mm, y + 4.2 * mm, 2.6 * mm, GREEN, 0.6)
    if site_host:
        c.setFillColor(MUTED)
        c.setFont("inter-400", 5)
        c.drawRightString(x + w - PAD, y + 1.6 * mm, site_host)

    if voucher.activated_at:
        c.saveState()
        c.setFillColor(white)
        c.setFillAlpha(0.55)
        c.roundRect(x, y, w, CARD_H, 3 * mm, stroke=0, fill=1)
        c.restoreState()
        c.saveState()
        c.translate(x + w / 2, y + CARD_H / 2)
        c.rotate(12)
        label = _("Imetumika").upper()
        lw = pdfmetrics.stringWidth(label, "inter-600", 10) + 5 * mm
        c.setStrokeColor(RED)
        c.setLineWidth(1.2)
        c.setFillColor(white)
        c.roundRect(-lw / 2, -3.2 * mm, lw, 6.4 * mm, 1.5 * mm, stroke=1, fill=1)
        c.setFillColor(RED)
        c.setFont("inter-600", 10)
        c.drawCentredString(0, -1.3 * mm, label)
        c.restoreState()


def render(owner, vouchers, site_host=""):
    """Rudisha bytes za PDF."""
    _register_fonts()
    buffer = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"{_('Vocha')} · {owner.business_name}")
    c.setAuthor(owner.business_name)
    card_w = (page_w - 2 * MARGIN - (COLS - 1) * GAP) / COLS
    rows = int((page_h - 2 * MARGIN + GAP) // (CARD_H + GAP))
    per_page = rows * COLS
    step_style = ParagraphStyle("step", fontName="inter-400", fontSize=6.3, leading=8, textColor=TEXT)
    logo = _logo(owner)
    for index, voucher in enumerate(vouchers):
        if index and index % per_page == 0:
            c.showPage()
        slot = index % per_page
        row, col = divmod(slot, COLS)
        x = MARGIN + col * (card_w + GAP)
        y = page_h - MARGIN - (row + 1) * CARD_H - row * GAP
        _card(c, x, y, card_w, voucher, owner, logo, site_host, step_style)
    c.save()
    return buffer.getvalue()
