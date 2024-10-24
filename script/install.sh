#! /bin/sh

set -e

cd "$(dirname "$0")/.."

echo "=> Installing picopy...\n"
sudo cp picopy.py /usr/local/bin/
sudo chmod +x /usr/local/bin/picopy.py

echo "=> Starting picopy...\n"
sudo cp picopy.sh /etc/init.d/
sudo chmod +x /etc/init.d/picopy.sh

sudo update-rc.d picopy.sh defaults
sudo /etc/init.d/picopy.sh start

echo "picopy installed.\n"