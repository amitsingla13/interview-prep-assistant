#!/bin/bash
# ============================================================
# Interview Prep Assistant — Oracle Cloud Setup Script
# Run this on your Oracle Cloud VM (Ubuntu)
# ============================================================
# Usage:
#   1. SSH into your VM: ssh -i your-key.pem ubuntu@YOUR_VM_IP
#   2. Copy this script: nano setup_server.sh  (paste contents, save)
#   3. Run: chmod +x setup_server.sh && ./setup_server.sh
# ============================================================

set -e

echo ""
echo "============================================================"
echo "  Interview Prep Assistant — Server Setup"
echo "============================================================"
echo ""

# --- 1. System updates and dependencies ---
echo "[1/6] Installing system dependencies..."
sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

# --- 2. Clone the repo ---
echo ""
echo "[2/6] Cloning the app..."
cd /home/ubuntu
if [ -d "interview-prep-assistant" ]; then
    echo "  Repo already exists, pulling latest..."
    cd interview-prep-assistant
    git pull
else
    git clone https://github.com/amitsingla13/interview-prep-assistant.git
    cd interview-prep-assistant
fi

# --- 3. Python environment ---
echo ""
echo "[3/6] Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- 4. Set up environment variables ---
echo ""
echo "[4/6] Setting up environment..."
if [ ! -f /home/ubuntu/interview-prep-assistant/.env ]; then
    read -p "  Enter your OpenAI API key (sk-proj-...): " OPENAI_KEY
    echo "OPENAI_API_KEY=${OPENAI_KEY}" > /home/ubuntu/interview-prep-assistant/.env
    echo "  API key saved to .env"
else
    echo "  .env already exists, skipping..."
fi

# --- 5. Create systemd service (auto-start on boot) ---
echo ""
echo "[5/6] Creating systemd service..."
sudo tee /etc/systemd/system/interview-app.service > /dev/null << 'EOF'
[Unit]
Description=Interview Prep Assistant
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/interview-prep-assistant
EnvironmentFile=/home/ubuntu/interview-prep-assistant/.env
ExecStart=/home/ubuntu/interview-prep-assistant/.venv/bin/gunicorn --worker-class eventlet -w 1 --chdir src app:app --bind 127.0.0.1:5000 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable interview-app
sudo systemctl start interview-app
echo "  App service started!"

# --- 6. Configure nginx reverse proxy ---
echo ""
echo "[6/6] Configuring nginx..."
sudo tee /etc/nginx/sites-available/interview-app > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/interview-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# --- 7. Configure firewall ---
echo ""
echo "Configuring firewall..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "  Your app is running at: http://$(curl -s ifconfig.me)"
echo ""
echo "  IMPORTANT: For the microphone to work on your phone,"
echo "  you need HTTPS. Run the SSL setup next:"
echo ""
echo "    ./setup_ssl.sh yourdomain.com"
echo ""
echo "  If you don't have a domain, you can use a free one from"
echo "  freenom.com or duckdns.org, or use nip.io:"
echo "    ./setup_ssl.sh YOUR_IP.nip.io"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status interview-app   # Check status"
echo "    sudo systemctl restart interview-app   # Restart app"
echo "    sudo journalctl -u interview-app -f    # View logs"
echo "============================================================"
