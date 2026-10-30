# Kuweka JamiiLite 5G hewani: Render + Supabase (bure, bila kadi)

Mfumo mzima unakaa sehemu mbili tu:

| Sehemu | Inakaa wapi |
|---|---|
| Website: ukurasa wa mwanzo, dashboard, superadmin, ukurasa wa kulipia, ripoti za routers | **Render** (Free) |
| Database na picha (logo) | **Supabase** (Free) |

**Hakuna RADIUS server wala VPS.** Kila router inahifadhi vocha zenyewe:

1. Mteja analipa, na JamiiLite inatengeneza vocha.
2. Router inaripoti kwa JamiiLite kila **sekunde 10** (HTTPS). Kwenye ripoti inayofuata,
   inapokea vocha mpya pamoja na muda na kasi yake.
3. Ukurasa wa kulipia unaonyesha "Tunakuunganisha…", kisha unamuunganisha mteja wenyewe.
4. Router inaripoti nani yuko online na data aliyotumia. Muda ukiisha, JamiiLite
   inaiambia router imtoe mteja.

Kwa sababu router ndiyo inayopiga simu, inafanya kazi hata nyuma ya 4G au NAT. Pia
routers zenyewe zinaiweka Render macho (haipati nafasi ya kulala).

> Render inachukua code kutoka branch `main`. Hakikisha mabadiliko yote yameingia `main`.

---

## Hatua 1: Supabase

1. Project mpya? Chagua region **East US (North Virginia)**, karibu na Render `virginia`.
   Project iliyopo ikiwa region nyingine, bado itafanya kazi, ila kurasa zitakuwa nzito kidogo.
2. **Connect → Session pooler** (port **5432**). Nakili connection string, na ubadilishe
   `[YOUR-PASSWORD]` kuwa password ya database. Hii ndiyo `DATABASE_URL`.
   Usitumie "Direct connection": inatumia IPv6 tu, na Render inatumia IPv4.
3. **Storage → New bucket** → `jamiilite-media` → washa **Public bucket**.
4. **Storage → Settings → S3 Connection**: nakili **Region**, kisha **New access key**
   (Access key ID na Secret access key). Secret inaonekana mara moja tu.
5. **Project ref** ni herufi zilizo baada ya `/project/` kwenye URL ya dashboard.

---

## Hatua 2: Render

1. <https://dashboard.render.com> → ingia kwa GitHub.
2. **New → Blueprint** → chagua repo **jamiilite-5g**, branch **main**.
   Render inasoma `render.yaml` na kuunda huduma `jamiilite` (plan Free).
3. Jaza thamani zinazoombwa:

   | Key | Weka |
   |---|---|
   | `DATABASE_URL` | Session pooler ya Supabase |
   | `JAMIILITE_PUBLIC_URL` | `https://jamiilite.onrender.com` (ihakiki kwenye hatua 5) |
   | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | acha wazi (jina la onrender.com linaongezwa lenyewe) |
   | `SUPABASE_PROJECT_REF`, `SUPABASE_S3_REGION`, `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY` | kutoka Supabase |
   | `JAMIILITE_WHATSAPP_NUMBER` | mfano `255712345678` (si lazima) |
   | `DJANGO_SUPERUSER_USERNAME` | mfano `admin` |
   | `DJANGO_SUPERUSER_PASSWORD` | password ndefu ya Super Admin |

4. **Apply**, kisha subiri build (dakika 3–6). Unaweza kuifuatilia kwenye **Logs**.
   Build inatengeneza tables za database na Super Admin wako yenyewe.
5. Juu ya ukurasa wa huduma kuna URL yako. Ikiwa ni tofauti, mfano
   `https://jamiilite-ab12.onrender.com`: **Environment** → badilisha `JAMIILITE_PUBLIC_URL` → **Save**.
6. Jaribu:
   - `https://<url>/healthz/` → `ok`
   - `https://<url>/control/` → ingia kama Super Admin
7. Usalama: **Environment** → futa `DJANGO_SUPERUSER_PASSWORD` (Super Admin ameshatengenezwa).

---

## Hatua 3: UptimeRobot

Routers zinaiweka Render macho. Lakini kabla router ya kwanza haijaunganishwa,
Render Free inalala baada ya dakika 15 bila mtu, na kuamka kunachukua karibu dakika 1.

<https://uptimerobot.com> → **Add New Monitor**:
- Type **HTTP(s)**, URL `https://<url>/healthz/`, interval **dakika 5**

`/healthz/` inakagua pia database. Ikijibu `503`, UptimeRobot itakutumia email.

> Render Free inatoa **saa 750 kwa mwezi** kwa akaunti nzima. Huduma moja inayowaka
> mwezi mzima inatumia takriban saa 744, kwa hiyo usiweke huduma nyingine ya bure
> kwenye akaunti hiyo hiyo.

---

## Hatua 4: Unganisha router

1. Jisajili kama mmiliki (`/jisajili/`) → **Routers** → ongeza router → nakili **mstari wa usanidi**.
2. Kwenye MikroTik: **Terminal** → bandika → Enter (angalia ukurasa wa **Mwongozo**).
   RouterOS **7.15 au zaidi** inahitajika. Router ikiwa na toleo la zamani, mstari wa usanidi utakuambia uisasishe kwanza.
3. Ndani ya sekunde chache router inaonekana **🟢 Online**.
4. Unganisha simu kwenye WiFi. Ukurasa wa kulipia unafunguka wenyewe → nunua kifurushi
   → "Tunakuunganisha…" → umeunganishwa.

Kukagua: **Superadmin → Hali ya mfumo**:
- **Uthibitishaji wa vocha** inaonyesha "Ndani ya router".
- **Superadmin → Routers → router** inaonyesha idadi ya **vocha kwenye router**.

---

## Hatua 5: Backup ya data

Supabase ya bure haikupi backup unazoweza kupakua, kwa hiyo backup iko ndani ya mfumo wenyewe:

**Superadmin → Hali ya mfumo → Pakua backup sasa.**

Faili moja (`jamiilite-<tarehe>.json.gz`) lina wamiliki, routers, vifurushi, vocha, malipo na salio.
Lipakue angalau mara moja kwa wiki, na kabla ya mabadiliko makubwa. Lihifadhi mahali salama
(mfano Google Drive yako, si kwenye chat wala mahali pa wazi): lina namba za simu za wateja.

**Kurudisha** kwenye database mpya (mfano project mpya ya Supabase):

```bash
# DATABASE_URL ya database mpya iwe kwenye .env
python manage.py migrate
python manage.py loaddata jamiilite-2026-10-30-0217.json.gz
```

Kisha badilisha `DATABASE_URL` ya Render kwenda database hiyo.

---

## Hatua 6: Sentry (si lazima, bure)

Kosa likitokea kwenye mfumo, Sentry inakutumia email pamoja na mahali hasa lilipotokea.

1. <https://sentry.io> → jisajili → **Create project** → Django → nakili **DSN**.
2. Render → **Environment** → `SENTRY_DSN` = DSN hiyo → **Save**.

Hakuna data ya wateja inayotumwa: hakuna IP, cookies, fomu (namba za simu, password), na siri
za routers kwenye anwani zinafichwa.

---

## Usalama

- **Routers zinahakiki server.** Kwenye usanidi wa kwanza, router inapakua vyeti vya msingi
  (Let's Encrypt na Google, `radius/trust/roots.pem`). Baada ya hapo, kila ripoti na kila amri
  inakataliwa kama cheti cha server si halali. Kwa hiyo saa ya router lazima iwe sahihi: usanidi
  unawasha NTP wenyewe. Ukihamia domain yenye cheti cha mtoa huduma mwingine, ongeza root CA yake
  kwenye faili hilo, kisha **Weka upya usanidi** kwa routers zote.
- **Majaribio mengi yanazuiwa:**
  - Kuingia: namba moja inapewa majaribio 5 kwa dakika 15, na IP moja 30.
  - Kujisajili: akaunti 10 kwa saa kutoka IP moja.
  - `/admin/`: majaribio 20 kwa dakika 15.
  - Kitufe cha "Lipa": namba moja inapewa maombi 3 kwa dakika 5.

  IP inasomwa kutoka `X-Forwarded-For` kwa kuzingatia `JAMIILITE_PROXY_HOPS`. Kwa Render
  chaguo-msingi ni `1`, na hakuna haja ya kuigusa.
- **Mstari wa usanidi ukivuja:** Routers → router → **Badilisha siri**, kisha bandika mstari mpya.

---

## Kusasisha mfumo

Render inajisasisha yenyewe kila code mpya inapoingia `main`. Routers hazihitaji kitu.
Kama mabadiliko yanagusa usanidi wa router, kwenye superadmin chagua router → **Weka upya usanidi**.

---

## Kabla ya wateja halisi ⚠️

- **Malipo bado ni sandbox:** kila mteja anapewa vocha **bila kulipa**. Ni kwa majaribio tu.
  Malipo halisi (Selcom / AzamPay / ClickPesa) yakiunganishwa, badilisha `PAYMENT_PROVIDER`
  na uweke `ALLOW_SANDBOX_PAYMENTS=False`.
- **Free tier haina uhakika wa 100%.** Wamiliki wakianza kulipa, Render Starter
  (takriban $7 kwa mwezi) inapendekezwa.
- **Mteja anasubiri sekunde chache** baada ya kulipa, mpaka router ipokee vocha
  (`JAMIILITE_CHECKIN_SECONDS`, chaguo-msingi 10). Ukipunguza, mteja anaunganishwa
  haraka zaidi, lakini server inapokea maombi mengi zaidi.

---

## Hiari: RADIUS server kwenye VPS

Ukipata VPS yenye UDP (Google Cloud, Oracle Cloud, Hetzner…), unaweza kutumia RADIUS badala
ya vocha zilizo ndani ya router. Faida ni kwamba mteja anaunganishwa papo hapo bila kusubiri ripoti.

1. Weka `JAMIILITE_AUTH_MODE=radius` na `RADIUS_PUBLIC_ADDRESS=<IP ya VPS>` kwenye Render.
2. Kwenye VPS (Ubuntu 24.04), fungua UDP `1812-1813` kwenye firewall ya mtoa huduma, kisha:
   ```bash
   git clone https://github.com/Barackwilliam/jamiilite-5g.git
   sudo bash jamiilite-5g/deploy/gcp/install.sh
   sudo nano /etc/jamiilite/radius.env      # SECRET_KEY na DATABASE_URL
   sudo systemctl restart jamiilite-radius
   ```
   `install.sh` inafungua pia firewall ya ndani ya Ubuntu ya Oracle (iptables) yenyewe.
3. Kwenye superadmin, chagua routers zote → **Weka upya usanidi**.
