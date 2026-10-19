# Kuweka JamiiLite 5G hewani: Render (free) + Google Cloud (free)

Mfumo una sehemu mbili, na kila moja inakaa mahali tofauti:

| Sehemu | Inakaa wapi | Kwa nini |
|---|---|---|
| Website: ukurasa wa mwanzo, dashboard, superadmin, ukurasa wa kulipia | **Render** (free) | Ni HTTPS ya kawaida |
| RADIUS: router inauliza "vocha hii ni halali?" | **Google Cloud e2-micro** (free) | Inatumia **UDP 1812/1813**, na Render haipokei UDP |
| Database na picha | **Supabase** | Zote mbili juu zinatumia database moja |

Zote tatu ziwe **mashariki ya Marekani** (Render `virginia`, Google `us-east1`,
Supabase `us-east-1`). Hivyo kila query ya database inachukua milisekunde chache.
Router iliyoko Tanzania inasubiri jibu la RADIUS hadi sekunde 3, na umbali huu
ni takriban robo sekunde tu.

> Kabla ya kuanza: Render na Google zinachukua code kutoka branch `main`.
> Hakikisha mabadiliko yote yameingia `main` (merge pull request).

---

## Hatua 1: Supabase

1. Kama unafungua project mpya, chagua region **East US (North Virginia)**.
   Project yako ya sasa ikiwa region nyingine bado itafanya kazi, ila kurasa
   zitakuwa nzito kidogo.
2. **Connect → Session pooler** (port **5432**). Nakili connection string:
   hii ndiyo `DATABASE_URL`. Usitumie "Direct connection": inatumia IPv6 tu,
   na Render na Google zinatumia IPv4.
3. Storage (logo za wamiliki): fuata sehemu ya *Storage* kwenye `README.md`
   ili upate `SUPABASE_PROJECT_REF`, `SUPABASE_S3_REGION`,
   `SUPABASE_S3_ACCESS_KEY_ID` na `SUPABASE_S3_SECRET_ACCESS_KEY`.

---

## Hatua 2: Google Cloud (RADIUS)

### 2.1 Fungua VM ya bure
1. Ingia <https://console.cloud.google.com>, fungua project mpya (mfano `jamiilite`).
   Watakuomba kadi ili kuthibitisha. Free tier haikukati pesa ukifuata hatua hizi.
2. **Compute Engine → VM instances → Create instance**:
   - **Name:** `jamiilite-radius`
   - **Region:** `us-east1` (South Carolina). Free tier ni `us-east1`, `us-central1` au `us-west1` **tu**.
   - **Machine type:** `e2-micro`
   - **Boot disk → Change:** Ubuntu **24.04 LTS**, aina **Standard persistent disk**, GB **30**.
     (Balanced au SSD zinatozwa.)
   - **Networking → Network tags:** andika `radius`
   - **Networking → Network interface → External IPv4 address → Reserve static external IP**,
     jina `jamiilite-radius-ip`. Hii ni lazima: routers zote zinaandikiwa IP hii.
3. **Create**. Nakili **External IP** (mfano `34.75.10.20`). Hii ndiyo `RADIUS_PUBLIC_ADDRESS`.

### 2.2 Fungua port za RADIUS
**VPC network → Firewall → Create firewall rule**:
- **Name:** `allow-radius`
- **Targets:** *Specified target tags* → `radius`
- **Source IPv4 ranges:** `0.0.0.0/0` (routers ziko nyuma ya 4G au NAT, kwa hiyo IP zao hazijulikani)
- **Protocols and ports:** *UDP* → `1812,1813`

Ni salama kufungua kwa wote: packet kutoka router isiyojulikana, au yenye
secret isiyo sahihi, inapuuzwa.

### 2.3 Weka RADIUS
Kwenye orodha ya VM bonyeza **SSH** (inafungua terminal kwenye browser), kisha:

```bash
git clone https://github.com/Barackwilliam/jamiilite-5g.git
sudo bash jamiilite-5g/deploy/gcp/install.sh
```

> Repo ikiwa **private**: GitHub → Settings → Developer settings →
> *Fine-grained tokens* → token ya **kusoma tu** (Contents: Read) kwa repo hii.
> Kisha tumia `https://<TOKEN>@github.com/Barackwilliam/jamiilite-5g.git` mahali pote
> pa URL, na uipe install.sh kama hoja ya kwanza:
> `sudo bash jamiilite-5g/deploy/gcp/install.sh https://<TOKEN>@github.com/Barackwilliam/jamiilite-5g.git`

Script itakuambia ujaze mipangilio:

```bash
sudo nano /etc/jamiilite/radius.env     # weka SECRET_KEY na DATABASE_URL
sudo systemctl restart jamiilite-radius
sudo journalctl -u jamiilite-radius -f  # unapaswa kuona "RADIUS inasikiliza 0.0.0.0:1812"
```

RADIUS inawaka yenyewe VM ikiwaka upya, na inajiwasha tena ikianguka.

### 2.4 Kinga ya bili (dakika 1)
**Billing → Budgets & alerts → Create budget**: kiasi **$1**, arifa kwa email.
Kitu kikianza kutozwa kwa bahati mbaya, utajua siku hiyo hiyo.

---

## Hatua 3: Render (website)

1. <https://dashboard.render.com> → **New → Blueprint** → unganisha GitHub, chagua repo hii.
   Render itasoma `render.yaml` na kuunda huduma `jamiilite` (plan Free).
2. Itakuomba thamani za siri:
   - `DATABASE_URL`: ile ile ya Session pooler
   - `RADIUS_PUBLIC_ADDRESS`: IP ya VM ya Google (hatua 2.1)
   - `JAMIILITE_PUBLIC_URL`: `https://jamiilite.onrender.com` (au jina Render litakalokupa)
   - `ALLOWED_HOSTS` na `CSRF_TRUSTED_ORIGINS`: acha wazi kama huna domain yako.
     Jina la `onrender.com` linaongezwa lenyewe.
   - Keys za Supabase Storage
   - `JAMIILITE_WHATSAPP_NUMBER`: mfano `255712345678` (si lazima)
3. **Apply**. Build inaendesha `migrate` yenyewe.
4. Fungua `https://jamiilite.onrender.com/healthz/`: unapaswa kuona `ok`.

### Superadmin wa kwanza
Render Free haina Shell, lakini VM ya Google inaunganishwa na database ile ile:

```bash
sudo /opt/jamiilite/deploy/gcp/manage.sh createsuperuser
```

Kisha ingia `https://jamiilite.onrender.com/control/`.

---

## Hatua 4: UptimeRobot (website isilale)

Render Free inalala baada ya dakika 15 bila mtu kuitembelea, na kuamka kunachukua
karibu dakika moja. Mteja aliyeunganishwa kwenye WiFi hawezi kusubiri hivyo.

<https://uptimerobot.com> → **Add New Monitor**:
- **Type:** HTTP(s)
- **URL:** `https://jamiilite.onrender.com/healthz/`
- **Interval:** dakika 5

`/healthz/` inakagua pia database: ikijibu `503`, UptimeRobot itakutumia email.

> Render Free inatoa **saa 750 kwa mwezi** kwa akaunti nzima. Huduma moja
> inayowaka mwezi mzima inatumia takriban saa 744, kwa hiyo **usiweke huduma
> nyingine ya bure** kwenye akaunti hiyo hiyo.

---

## Hatua 5: Unganisha router

1. Ingia dashboard kama mmiliki → **Routers** → ongeza router → nakili **mstari wa usanidi**.
2. Bandika kwenye Terminal ya MikroTik (angalia ukurasa wa **Mwongozo**).
3. Router iliyosanidiwa zamani kwa anwani nyingine: kwenye superadmin chagua
   router → **Weka upya usanidi wa JamiiLite**.

Kukagua: **Superadmin → System status**. RADIUS inapaswa kuwa ya kijani
(inaripoti kila sekunde 30), na router iwe **Online** ndani ya dakika moja.

---

## Kusasisha mfumo

- **Website:** Render inajisasisha yenyewe kila unaposukuma code kwenye `main`.
- **RADIUS:** kwenye VM endesha tena:
  ```bash
  sudo bash /opt/jamiilite/deploy/gcp/install.sh
  ```

---

## Kabla ya wateja halisi ⚠️

- **Malipo bado ni sandbox:** kila mteja anapewa vocha **bila kulipa**. Ni kwa
  majaribio tu. Malipo halisi (Selcom / AzamPay / ClickPesa) yakiunganishwa,
  badilisha `PAYMENT_PROVIDER` kwenye Render na uweke `ALLOW_SANDBOX_PAYMENTS=False`.
- **Free tier haina uhakika wa 100%:** UptimeRobot ikikosa ping moja, au Render
  ikiwasha upya huduma, ukurasa wa kulipia unaweza kuchelewa kwa dakika moja.
  Wamiliki wakianza kulipa, hamia mpango wa kulipia wa Render (takriban $7 kwa
  mwezi), au weka kila kitu kwenye VPS moja.
- **Google e2-micro:** data ya bure ni GB 1 kwa mwezi. RADIUS inatumia MB chache
  tu, kwa hiyo usiweke kitu kingine kwenye VM hiyo.
