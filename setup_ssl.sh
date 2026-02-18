#!/bin/bash
# ============================================================
# SSL Setup for Interview Prep Assistant
# This enables HTTPS so the microphone works on mobile browsers
# ============================================================
# Usage: ./setup_ssl.sh yourdomain.com
#   or:  ./setup_ssl.sh YOUR_VM_IP.nip.io  (free, no domain needed)
# ============================================================

set -e

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo ""
    echo "Usage: ./setup_ssl.sh <domain>"
    echo ""
    echo "Options:"
    echo "  1. If you have a domain: ./setup_ssl.sh yourdomain.com"
    echo "  2. Free without domain:  ./setup_ssl.sh $(curl -s ifconfig.me).nip.io"
    echo ""
    exit 1
fi

echo ""
echo "Setting up SSL for: $DOMAIN"
echo ""

# Update nginx config with the domain
sudo tee /etc/nginx/sites-available/interview-app > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF

sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate from Let's Encrypt
echo "Getting SSL certificate..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

echo ""
echo "============================================================"
echo "  SSL SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "  Your app is now available at:"
echo "  https://$DOMAIN"
echo ""
echo "  Open this URL on your phone — mic will work!"
echo "  Certificate auto-renews via certbot."
echo "============================================================"
