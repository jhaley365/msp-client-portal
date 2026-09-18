#!/bin/bash
set -a
source /etc/msp-portal/sync.env
set +a
exec /opt/msp-portal/.venv/bin/python -c "
from app.services.ec2_inventory_sync import lambda_handler
lambda_handler({}, None)
" >> /var/log/msp-portal-ec2-sync.log 2>&1
