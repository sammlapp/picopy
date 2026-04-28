#! /bin/sh

set -e

cd "$(dirname "$0")/.."

echo "=> Installing picopy...\n"
sudo cp picopy.py /usr/local/bin/
sudo chmod +x /usr/local/bin/picopy.py

sudo cp picopy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable picopy.service

echo "picopy installed.\n"

echo "=> Installing listen-for-shutdown...\n"
sudo cp listen-for-shutdown.py /usr/local/bin/
sudo chmod +x /usr/local/bin/listen-for-shutdown.py

sudo cp listen-for-shutdown.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable listen-for-shutdown.service

echo "listen-for-shutdown installed.\n"

echo "=> Starting picopy...\n"
sudo systemctl start picopy.service

echo "=> Starting listen-for-shutdown...\n"
sudo systemctl start listen-for-shutdown.service

