"""
Mwongozo wa kuunganisha MikroTik (PDF), kwa Kiswahili na Kiingereza.
Tengeneza upya:  python docs/guide/build.py   (inahitaji Playwright + Chromium)
Matokeo: static/docs/mwongozo-jamiilite-sw.pdf na static/docs/mwongozo-jamiilite-en.pdf
"""
import base64
import pathlib
import subprocess
import json

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONTS = {n: base64.b64encode((ROOT / "static/fonts" / f"{n}.woff2").read_bytes()).decode()
         for n in ("sora-800", "sora-700", "inter-400", "inter-600")}
WHATSAPP = "0750 910 158"
SITE = "wifi.jamiitek.co.tz"

T = {
 "sw": dict(
  title="Unganisha MikroTik yako na JamiiLite 5G", sub="Hatua 8 rahisi · takribani dakika 10 · simu inatosha",
  before="Kabla hujaanza", before_items=["MikroTik (mfano hAP lite) na waya wake wa umeme", "Router yako ya internet (4G/5G au fiber) inayofanya kazi", f"Akaunti ya JamiiLite 5G ({SITE})", "Waya mmoja wa mtandao (LAN)"],
  step="Hatua",
  steps=[
   ("Chomeka waya", ["Upande mmoja wa waya: kwenye router yako ya internet.", "Upande mwingine: kwenye tundu la <b>KWANZA</b> la MikroTik (namba 1).", "Washa MikroTik, kisha subiri dakika 1."]),
   ("Pakua app ya MikroTik", ["Fungua <b>Play Store</b> au <b>App Store</b>.", "Tafuta <b>MikroTik</b>, pakua app rasmi (ni bure).", "Una kompyuta? Unaweza kutumia <b>Winbox</b> badala yake."]),
   ("Unganisha simu na MikroTik", ["Fungua WiFi ya simu yako.", "Chagua WiFi inayoanza na <b>MikroTik-</b>.", "Ikiuliza password, iko kwenye kibandiko chini ya MikroTik."]),
   ("Ingia kwenye MikroTik", ["Fungua app ya MikroTik.", "Anwani: <code>192.168.88.1</code> · Jina: <code>admin</code>", "Password: ya kwenye kibandiko (MikroTik za zamani: acha wazi).", "Bonyeza <b>Connect</b>."]),
   ("Chukua mstari wa usanidi", [f"Kwenye simu hiyo hiyo, fungua <b>{SITE}</b> na uingie.", "Nenda <b>Routers</b> › <b>Ongeza router</b>.", "Andika jina la eneo na jina la WiFi wateja watakaloliona, kisha Hifadhi.", "Bonyeza <b>Nakili</b> kunakili mstari mrefu unaoonekana."]),
   ("Bandika mstari kwenye MikroTik", ["Rudi kwenye app ya MikroTik, fungua <b>Terminal</b>.", "Bonyeza kwa muda mrefu ndani ya Terminal, chagua <b>Paste</b>.", "Bonyeza <b>Enter</b>, subiri sekunde chache.", "Utaona: <code>JamiiLite: usanidi umekamilika</code>"]),
   ("Hakikisha imeunganishwa", [f"Rudi {SITE} kwenye ukurasa wa router yako.", "Ndani ya dakika 1 utaona <b class='ok'>● Online</b>.", "Hongera! MikroTik yako imeunganishwa."]),
   ("Jaribu kama mteja", ["Chukua simu nyingine, unganisha kwenye WiFi yako mpya.", "Ukurasa wa vifurushi utafunguka wenyewe.", "Nunua kifurushi cha bei ndogo kuhakikisha malipo yanafanya kazi."]),
  ],
  secret="Mstari wa usanidi ni <b>siri yako</b>. Usimtumie mtu yeyote wala kuuweka kwenye makundi. Ukivuja, bonyeza <b>Badilisha siri</b> kwenye ukurasa wa router.",
  help_title="Ukikwama", help=[
   ("Haioni WiFi ya “MikroTik-”", "Subiri dakika 2 baada ya kuwasha. Bado? Fanya <b>Reset</b>: zima MikroTik, shikilia kitufe cha RESET, washa, endelea kushikilia sekunde 5 hadi taa iwake-zime, kisha achia."),
   ("Inasema RouterOS ni ya zamani", "Kwenye app: <b>System › Packages › Check For Updates › Download &amp; Install</b>. Ikiwaka tena, rudia Hatua 6."),
   ("Haionyeshi Online baada ya dakika 2", "Hakikisha waya uko kwenye tundu namba 1 na internet inafanya kazi, kisha bandika mstari tena (Hatua 6)."),
   ("MikroTik ilishatumika kwingine", "Ifanyie Reset kwanza (kama juu), kisha anza Hatua 3."),
  ],
  contact=f"Bado umekwama? Tuma screenshot WhatsApp <b>{WHATSAPP}</b>", footer=f"JamiiLite 5G · {SITE}",
 ),
 "en": dict(
  title="Connect your MikroTik to JamiiLite 5G", sub="8 simple steps · about 10 minutes · a phone is enough",
  before="Before you start", before_items=["A MikroTik (e.g. hAP lite) and its power cable", "Your internet router (4G/5G or fiber), working", f"A JamiiLite 5G account ({SITE})", "One network (LAN) cable"],
  step="Step",
  steps=[
   ("Plug in the cable", ["One end of the cable: into your internet router.", "Other end: into the <b>FIRST</b> port of the MikroTik (number 1).", "Turn the MikroTik on and wait 1 minute."]),
   ("Get the MikroTik app", ["Open <b>Play Store</b> or <b>App Store</b>.", "Search <b>MikroTik</b> and install the official app (free).", "On a computer you can use <b>Winbox</b> instead."]),
   ("Connect your phone to the MikroTik", ["Open your phone's WiFi.", "Pick the network starting with <b>MikroTik-</b>.", "If it asks for a password, it is on the sticker under the MikroTik."]),
   ("Log in to the MikroTik", ["Open the MikroTik app.", "Address: <code>192.168.88.1</code> · User: <code>admin</code>", "Password: from the sticker (older models: leave empty).", "Tap <b>Connect</b>."]),
   ("Get your setup line", [f"On the same phone, open <b>{SITE}</b> and log in.", "Go to <b>Routers</b> › <b>Add router</b>.", "Enter a place name and the WiFi name customers will see, then Save.", "Tap <b>Copy</b> to copy the long line you see."]),
   ("Paste the line into the MikroTik", ["Back in the MikroTik app, open <b>Terminal</b>.", "Long-press inside Terminal and choose <b>Paste</b>.", "Press <b>Enter</b> and wait a few seconds.", "You will see: <code>JamiiLite: usanidi umekamilika</code>"]),
   ("Check it is connected", [f"Go back to {SITE}, on your router's page.", "Within 1 minute you will see <b class='ok'>● Online</b>.", "Well done! Your MikroTik is connected."]),
   ("Try it as a customer", ["Take another phone and join your new WiFi.", "The packages page opens by itself.", "Buy the cheapest package to confirm payments work."]),
  ],
  secret="The setup line is <b>your secret</b>. Don't send it to anyone or post it in groups. If it leaks, tap <b>Change secret</b> on the router page.",
  help_title="If you get stuck", help=[
   ("No “MikroTik-” WiFi", "Wait 2 minutes after power-on. Still nothing? <b>Reset</b>: power off, hold the RESET button, power on, keep holding 5 seconds until the light flashes, then release."),
   ("It says RouterOS is too old", "In the app: <b>System › Packages › Check For Updates › Download &amp; Install</b>. When it restarts, repeat Step 6."),
   ("Not Online after 2 minutes", "Check the cable is in port 1 and the internet works, then paste the line again (Step 6)."),
   ("The MikroTik was used before", "Reset it first (as above), then start from Step 3."),
  ],
  contact=f"Still stuck? Send a screenshot on WhatsApp <b>{WHATSAPP}</b>", footer=f"JamiiLite 5G · {SITE}",
 ),
}

CSS = """
@font-face{font-family:Sora;font-weight:800;src:url(data:font/woff2;base64,@@sora-800@@)}
@font-face{font-family:Sora;font-weight:700;src:url(data:font/woff2;base64,@@sora-700@@)}
@font-face{font-family:Inter;font-weight:400;src:url(data:font/woff2;base64,@@inter-400@@)}
@font-face{font-family:Inter;font-weight:600;src:url(data:font/woff2;base64,@@inter-600@@)}
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font:400 10.5pt/1.45 Inter,sans-serif;color:#14213d;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:297mm;padding:0 0 14mm;position:relative;page-break-after:always;overflow:hidden}
.page:last-child{page-break-after:auto}
.hero{background:radial-gradient(400px 260px at 95% 0,rgba(0,90,200,.6),transparent 70%),linear-gradient(160deg,#01081A,#06204A);color:#fff;padding:11mm 16mm 9mm}
.brand{display:flex;align-items:center;gap:10px;font:800 15pt Sora}.brand i{width:30px;height:30px;border-radius:9px;background:linear-gradient(140deg,#FFB627,#FF7A3D);display:grid;place-items:center}
.brand b{color:#F5A623}
h1{font:800 22pt/1.15 Sora;letter-spacing:-.02em;margin-top:6mm;max-width:178mm}
.sub{color:#A7B3CA;margin-top:3mm;font-size:11pt}
.before{margin:5mm 16mm 0;padding:4mm 6mm;border-radius:12px;background:#FFF6E6;border:1px solid #F5D49A}
.before h2{font:800 11pt Sora;color:#A35A00;margin-bottom:2mm}
.before ul{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:1.5mm 6mm}
.before li:before{content:"✓ ";color:#E8890C;font-weight:700}
.steps{margin:5mm 16mm 0;display:grid;grid-template-columns:1fr 1fr;gap:4mm}
.st{border:1px solid #DDE3EE;border-radius:14px;padding:4mm 4.5mm;break-inside:avoid;background:#fff}
.st header{display:flex;align-items:center;gap:3mm;margin-bottom:2.5mm}
.st .n{flex:none;width:9mm;height:9mm;border-radius:50%;display:grid;place-items:center;font:800 12pt Sora;color:#2A1702;background:linear-gradient(140deg,#FFB627,#FF7A3D)}
.st small{display:block;font:600 7.5pt Inter;color:#8592ab;text-transform:uppercase;letter-spacing:.08em}
.st h3{font:800 11.5pt/1.2 Sora}
.st ul{list-style:none;display:grid;gap:1.4mm}
.st li{padding-left:4mm;position:relative}.st li:before{content:"";position:absolute;left:0;top:2.2mm;width:1.6mm;height:1.6mm;border-radius:50%;background:#22B8E0}
code{font:600 9.5pt ui-monospace,Menlo,monospace;background:#EEF2F9;padding:.3mm 1.5mm;border-radius:4px}
.ok{color:#15803d}
.secret{margin:5mm 16mm 0;padding:4mm 5mm;border-radius:12px;background:#FDECEC;color:#8a1c12;border:1px solid #f5b4ac;display:flex;gap:3mm;align-items:flex-start}
.help{margin:6mm 16mm 0}
.help h2{font:800 14pt Sora;margin-bottom:3mm}
.q{padding:3.5mm 0;border-bottom:1px solid #E5E9F1;break-inside:avoid}.q b.t{display:block;font:700 10.5pt Sora;margin-bottom:1mm}
.contact{margin:6mm 16mm 0;padding:5mm 6mm;border-radius:14px;background:linear-gradient(160deg,#01081A,#06204A);color:#fff;font-size:12pt;display:flex;align-items:center;gap:4mm}
.contact b{color:#FFB627}
.foot{position:absolute;left:16mm;right:16mm;bottom:7mm;display:flex;justify-content:space-between;color:#8592ab;font-size:8pt;border-top:1px solid #E5E9F1;padding-top:2.5mm}
"""
for _n, _b in FONTS.items():
    CSS = CSS.replace("@@" + _n + "@@", _b)

WIFI = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2A1702" stroke-width="2.6" stroke-linecap="round"><path d="M2 9a15 15 0 0 1 20 0"/><path d="M5.5 12.5a10 10 0 0 1 13 0"/><path d="M9 16a5 5 0 0 1 6 0"/><circle cx="12" cy="19.5" r="1.3" fill="#2A1702" stroke="none"/></svg>'


def page(lang):
    t = T[lang]
    step = lambda i, s: f'<section class="st"><header><span class="n">{i}</span><div><small>{t["step"]} {i}</small><h3>{s[0]}</h3></div></header><ul>' + "".join(f"<li>{x}</li>" for x in s[1]) + "</ul></section>"
    brand = f'<div class="brand"><i>{WIFI}</i>JamiiLite <b>5G</b></div>'
    p1 = (f'<div class="page"><div class="hero">{brand}<h1>{t["title"]}</h1><p class="sub">{t["sub"]}</p></div>'
          f'<div class="before"><h2>{t["before"]}</h2><ul>' + "".join(f"<li>{x}</li>" for x in t["before_items"]) + "</ul></div>"
          '<div class="steps">' + "".join(step(i + 1, s) for i, s in enumerate(t["steps"][:6])) + "</div>"
          f'<div class="foot"><span>{t["footer"]}</span><span>1 / 2</span></div></div>')
    p2 = ('<div class="page" style="padding-top:14mm"><div class="steps" style="margin-top:0">' + "".join(step(i + 7, s) for i, s in enumerate(t["steps"][6:])) + "</div>"
          f'<div class="secret"><span>⚠️</span><span>{t["secret"]}</span></div>'
          f'<div class="help"><h2>{t["help_title"]}</h2>' + "".join(f'<div class="q"><b class="t">{q}</b>{a}</div>' for q, a in t["help"]) + "</div>"
          f'<div class="contact"><span style="font-size:18pt">💬</span><span>{t["contact"]}</span></div>'
          f'<div class="foot"><span>{t["footer"]}</span><span>2 / 2</span></div></div>')
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{p1}{p2}</body></html>'


if __name__ == "__main__":
    out = ROOT / "static/docs"
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for lang in T:
        html = pathlib.Path(f"/tmp/jamiilite-guide-{lang}.html")
        html.write_text(page(lang), encoding="utf-8")
        jobs.append({"html": str(html), "pdf": str(out / f"mwongozo-jamiilite-{lang}.pdf")})
    script = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
              f"for(const j of {json.dumps(jobs)}){{const p=await b.newPage();await p.goto('file://'+j.html);"
              "await p.waitForTimeout(300);await p.pdf({path:j.pdf,format:'A4',printBackground:true});await p.close();}"
              "await b.close();})();")
    subprocess.run(["node", "-e", script], check=True)
    for j in jobs:
        print(j["pdf"])
