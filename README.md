# JamiiLite 5G

Mfumo wa kusimamia biashara ya WiFi hotspot kwa wamiliki wa routers (MikroTik):
kuuza vifurushi, kupokea malipo ya simu, kutoa vocha, na kumkata mteja muda
ukiisha.

<img src="docs/portal-1-vifurushi.png" width="260" alt="Ukurasa wa kununua kifurushi"> <img src="docs/portal-2-vocha.png" width="260" alt="Vocha baada ya kulipa">

## Hali ya sasa

- **Wamiliki, routers na vifurushi** kupitia admin panel (`/admin/`)
- **Ukurasa wa kulipia** kwa Kiswahili kwa kila router: `/p/<kitambulisho>/`
- **Malipo ya majaribio (sandbox)**: kila malipo yanafanikiwa papo hapo, kisha mteja anapewa vocha
- **RADIUS server** (`python manage.py radius_server`): MikroTik inauliza mfumo huu kama vocha ni halali
  - muda wa **kalenda** (vocha ya saa 1 inaisha saa 1 baada ya kuanza, hata mteja akikatika)
  - **kasi** ya kifurushi inatumwa kwa MikroTik (Mikrotik-Rate-Limit)
  - vocha moja inakubaliwa kwenye idadi ya **vifaa** iliyowekwa kwenye kifurushi tu
  - vocha ya mmiliki inafanya kazi kwenye routers zake zote
- Database: **Supabase Postgres**. Picha (logo): **Supabase Storage**

Kinachofuata: malipo halisi (Selcom / AzamPay / ClickPesa) na dashboard ya mmiliki.

## Kuanza (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # kisha jaza thamani zako
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo    # data ya mfano
python manage.py runserver
```

Fungua `http://127.0.0.1:8000/p/demo/` kuona ukurasa wa kulipia, na
`http://127.0.0.1:8000/admin/` kwa usimamizi.

Bila `DATABASE_URL`, na `DEBUG=True`, mfumo unatumia SQLite. Bila keys za
Supabase Storage, picha zinahifadhiwa kwenye folda `media/`.

## Kuunganisha na Supabase

### 1. Database
Supabase Dashboard → **Connect** → nakili **Session pooler** connection string
(port 5432) na uiweke kama `DATABASE_URL` kwenye `.env`. Kisha:

```bash
python manage.py migrate
```

> **Usalama:** Supabase inaweka schema `public` wazi kupitia Data API. Baada ya
> kila `migrate`, mfumo huu unawasha **RLS** kwenye kila table ya `public` na
> kuondoa ruhusa za `anon` na `authenticated` (angalia `core/supabase.py`).
> Kwa hiyo malipo, vocha na RADIUS secrets haziwezi kusomwa kwa anon key.
> Django yenyewe inaunganishwa kama mmiliki wa tables, kwa hiyo haiathiriki.
> Ukiongeza tables kwa mkono kupitia SQL Editor, endesha `migrate` tena au
> washa RLS mwenyewe.

### 2. Storage (picha)
1. **Storage → New bucket** → jina `jamiilite-media` → weka **Public bucket** ✅
2. **Storage → Settings → S3 Connection**: nakili **Region**, kisha
   **New access key** ili upate *Access key ID* na *Secret access key*
3. Jaza kwenye `.env`:
   ```
   SUPABASE_PROJECT_REF=abcdefghijklmnop     # kutoka kwenye URL ya project
   SUPABASE_STORAGE_BUCKET=jamiilite-media
   SUPABASE_S3_REGION=...
   SUPABASE_S3_ACCESS_KEY_ID=...
   SUPABASE_S3_SECRET_ACCESS_KEY=...
   ```

S3 keys zina ruhusa kamili juu ya Storage. Ziweke kwenye server tu, kamwe
zisiwe kwenye browser au git.

## Kuunganisha na MikroTik

Mfumo una sehemu mbili zinazoendeshwa kwa pamoja, kila moja kwenye terminal
yake:

```bash
python manage.py runserver            # ukurasa wa kulipia + admin
python manage.py radius_server        # RADIUS (UDP 1812 na 1813)
```

### Usanidi wa mstari mmoja

Kila router ina **mstari mmoja** wa usanidi. Unauona kwenye admin (fungua
router, sehemu ya *Usanidi*), au kwa:

```bash
python manage.py mikrotik_config demo          # mstari mmoja
python manage.py mikrotik_config demo --full   # script nzima, kwa kuikagua
```

Mstari huo ukibandikwa kwenye terminal ya MikroTik, unapakua usanidi kutoka
`/r/<token>/setup.rsc` na kuuweka:
1. **Jina la router** (`/system identity`), sawa na *NAS identifier* yake
2. **RADIUS** pamoja na secret ya router hiyo
3. **Login kwa PAP**: vocha inatumwa kama username na password
4. **Walled garden**: mteja anafikia ukurasa wa kulipia kabla hajaingia
5. **`hotspot/login.html`**: inampeleka mteja kwenye ukurasa wetu
6. **Ripoti ya kila dakika (check-in)**: angalia hapa chini

Ni salama kuuendesha tena: unaondoa mipangilio ya zamani ya JamiiLite kabla ya
kuweka mipya. Router lazima iwe na hotspot tayari.

### Router "inapiga simu nyumbani"

Kila dakika router inatuma ripoti (`/r/<token>/checkin`): toleo la RouterOS,
muda iliowaka, na wateja walio online. Admin inaonyesha router iko
**Online/Offline**. Kwa sababu router ndiyo inayoanzisha mawasiliano, hii
inafanya kazi hata nyuma ya 4G au NAT.

Jibu la ripoti linabeba **maagizo kutoka mbali**. Kwenye admin, chagua routers,
kisha *Actions*:
- **Washa upya (reboot)**
- **Weka upya usanidi wa JamiiLite**: router inapakua usanidi mpya, kwa mfano
  baada ya kubadilisha anwani ya server

Token ya usanidi ni siri: yeyote mwenye link anaweza kuona RADIUS secret ya
router. Kwenye server halisi tumia **HTTPS** tu.

### Anwani

Kwa chaguo-msingi, anwani ni zile za maabara ya VirtualBox: MikroTik inaiona
kompyuta mwenyeji kama `10.0.2.2` (weka `10.0.2.2` kwenye `ALLOWED_HOSTS`).
Kwa server halisi weka kwenye `.env`:

```
JAMIILITE_PUBLIC_URL=https://jamiilite.example.com
RADIUS_PUBLIC_ADDRESS=203.0.113.10
```

**Usalama:**
- Packet kutoka router isiyojulikana, au yenye secret batili, inapuuzwa.
- Maombi bila **Message-Authenticator** yanakataliwa (kinga dhidi ya
  BlastRADIUS). RouterOS 7.15 na kuendelea inaituma. Kwa router za zamani
  weka `RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR=False`.
- Ukiweka **login URL ya hotspot** kwenye router (admin), vocha zinatumwa hapo
  tu, na `link-login-only` inayokuja kwenye link inapuuzwa. Hii inazuia mtu
  kutengeneza link inayotuma vocha kwa server nyingine.

## Majaribio

```bash
DEBUG=True python manage.py test
```

## Muundo

| Folda | Kazi |
|---|---|
| `config/` | Settings (Supabase Postgres + Storage), URLs |
| `core/` | Wamiliki, routers, vifurushi, ulinzi wa RLS |
| `billing/` | Malipo, vocha, watoa huduma wa malipo (`providers/`) |
| `portal/` | Ukurasa wa kulipia anaouona mteja |
| `radius/` | RADIUS server na amri za kusanidi MikroTik |
