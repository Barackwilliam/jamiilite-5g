#!/usr/bin/env bash
# Endesha amri za Django kwenye VM ukitumia mipangilio ya /etc/jamiilite/radius.env.
# Mfano:  sudo /opt/jamiilite/deploy/gcp/manage.sh createsuperuser
set -euo pipefail
set -a
. /etc/jamiilite/radius.env
set +a
cd /opt/jamiilite
exec sudo -E -u jamiilite /opt/jamiilite/.venv/bin/python manage.py "$@"
