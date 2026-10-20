#!/usr/bin/env bash
# Inaweka RADIUS ya JamiiLite 5G kwenye VM ya Ubuntu 24.04 (Google Cloud, Oracle Cloud au VPS yoyote).
# Matumizi:  sudo bash install.sh [REPO_URL] [BRANCH]
# Ni salama kuiendesha tena: inasasisha code na kuwasha huduma upya.
set -euo pipefail

REPO_URL="${1:-https://github.com/Barackwilliam/jamiilite-5g.git}"
BRANCH="${2:-main}"
APP_DIR=/opt/jamiilite
ENV_DIR=/etc/jamiilite
ENV_FILE="$ENV_DIR/radius.env"

if [ "$(id -u)" -ne 0 ]; then echo "Endesha kwa sudo."; exit 1; fi

echo "==> Programu zinazohitajika"
apt-get update -qq
apt-get install -y -qq python3 python3-venv git >/dev/null

# e2-micro ina RAM ya 1GB tu: swap inazuia pip au server kukwama.
if ! swapon --show | grep -q /swapfile; then
  echo "==> Swap ya 1GB"
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# Picha za Ubuntu za Oracle Cloud zina iptables inayokataa kila port isipokuwa SSH.
# Kwenye Google na VPS nyingi faili hili halipo, kwa hiyo hatua hii inarukwa.
if [ -f /etc/iptables/rules.v4 ] && command -v iptables >/dev/null; then
  if ! iptables -C INPUT -p udp --dport 1812:1813 -j ACCEPT 2>/dev/null; then
    echo "==> Firewall ya ndani: fungua UDP 1812-1813"
    iptables -I INPUT -p udp --dport 1812:1813 -j ACCEPT
    if command -v netfilter-persistent >/dev/null; then
      netfilter-persistent save >/dev/null
    else
      iptables-save > /etc/iptables/rules.v4
    fi
  fi
fi

id jamiilite >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin jamiilite

echo "==> Code ($BRANCH)"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch -q origin "$BRANCH"
  git -C "$APP_DIR" checkout -q "$BRANCH"
  git -C "$APP_DIR" reset -q --hard "origin/$BRANCH"
else
  git clone -q --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "==> Python packages"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R jamiilite:jamiilite "$APP_DIR"

mkdir -p "$ENV_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP_DIR/deploy/gcp/radius.env.example" "$ENV_FILE"
fi
chown root:jamiilite "$ENV_FILE"
chmod 640 "$ENV_FILE"

cp "$APP_DIR/deploy/gcp/jamiilite-radius.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q jamiilite-radius

if grep -q BADILISHA "$ENV_FILE"; then
  echo
  echo "Karibu umalize! Jaza $ENV_FILE:"
  echo "  sudo nano $ENV_FILE"
  echo "kisha:"
  echo "  sudo systemctl restart jamiilite-radius"
  exit 0
fi

systemctl restart jamiilite-radius
sleep 3
systemctl --no-pager --lines=5 status jamiilite-radius || true
echo
echo "RADIUS iko hewani. Kuona kumbukumbu: sudo journalctl -u jamiilite-radius -f"
