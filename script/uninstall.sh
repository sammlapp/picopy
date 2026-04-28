#! /bin/sh

set -e

cd "$(dirname "$0")/.."

echo "=> Stopping picopy...\n"
sudo systemctl stop picopy.service
sudo systemctl disable picopy.service

echo "=> Removing picopy...\n"
sudo rm -f /usr/local/bin/picopy.py
sudo rm -f /etc/systemd/system/picopy.service
sudo systemctl daemon-reload

echo "picopy uninstalled.\n"