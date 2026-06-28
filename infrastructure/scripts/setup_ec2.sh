#!/usr/bin/env bash
# EC2 server setup script — run once on a fresh Amazon Linux 2023 or Ubuntu 22.04 instance.
# Usage: sudo bash setup_ec2.sh
set -euo pipefail

APP_DIR="/opt/msp-portal"
REPO_URL="${REPO_URL:-https://github.com/jhaley365/msp-client-portal.git}"
BRANCH="${BRANCH:-claude/practical-sagan-kkwh99}"
DOMAIN="${DOMAIN:-}"   # Set to your domain name for Nginx server_name

echo "==> Installing system packages"
if command -v dnf &>/dev/null; then
    dnf install -y python3.12 python3.12-pip python3.12-devel nginx git nodejs npm
else
    apt-get update -y
    apt-get install -y python3.12 python3.12-venv python3-pip nginx git nodejs npm
fi

echo "==> Cloning repository"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" pull origin "$BRANCH"
else
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "==> Setting up Python virtual environment"
python3.12 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "==> Building React frontend"
cd "$APP_DIR/frontend"
npm ci
npm run build

echo "==> Writing systemd service"
cat > /etc/systemd/system/msp-portal.service <<EOF
[Unit]
Description=MSP Client Portal API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$APP_DIR/backend
Environment="PYTHONPATH=$APP_DIR/backend"
Environment="JWT_SECRET_KEY=$(openssl rand -hex 32)"
Environment="DYNAMODB_REGION=us-east-1"
Environment="CORS_ORIGINS=http://${DOMAIN:-localhost}"
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> Writing Nginx config"
NGINX_CONF="/etc/nginx/conf.d/msp-portal.conf"
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${DOMAIN:- _};

    # React frontend
    root $APP_DIR/frontend/dist;
    index index.html;

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    # React Router — serve index.html for all non-asset paths
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|svg|ico|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

echo "==> Enabling and starting services"
systemctl daemon-reload
systemctl enable --now msp-portal
systemctl enable --now nginx
nginx -t && systemctl reload nginx

echo ""
echo "✅ Setup complete!"
echo "   API:      http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/api/health"
echo "   Frontend: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/"
echo ""
echo "⚠️  Remember to:"
echo "   1. Edit /etc/systemd/system/msp-portal.service and set a permanent JWT_SECRET_KEY"
echo "   2. Open port 80 (and 443) in your EC2 security group"
echo "   3. Point your domain DNS to this instance's public IP"
