#!/bin/bash
set -a
source /etc/msp-portal/sync.env
set +a
export PYTHONPATH=/opt/msp-portal/backend
exec /opt/msp-portal/.venv/bin/python3 -c "
import sys, json, logging
logging.basicConfig(level=logging.INFO)
mod = sys.argv[1]
__import__(mod)
import importlib
m = importlib.import_module(mod)
r = m.lambda_handler({}, None)
print(json.loads(r['body']))
" "$1"
