#!/bin/bash
set -a
source /etc/msp-portal/sync.env
set +a
exec /opt/msp-portal/.venv/bin/python -c "
from app.services.syncro_sync import lambda_handler
lambda_handler({}, None)
" >> /var/log/msp-portal-syncro-sync.log 2>&1
