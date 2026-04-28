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

echo "=> Starting picopy...\n"
sudo systemctl start picopy.service

