#!/bin/bash
set -e

REPO_DIR="/home/ubuntu/msp-client-portal"
BRANCH="claude/practical-sagan-kkwh99"
FRONTEND_DIR="$REPO_DIR/frontend"

echo "==> Pulling latest code..."
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> Building frontend..."
cd "$FRONTEND_DIR"
npm install
npm run build

echo "==> Restarting services..."
sudo systemctl restart msp-portal

echo "==> Done."
