#! /bin/sh

set -e

cd "$(dirname "$0")/.."

echo "=> Stopping picopy...\n"
sudo update-rc.d picopy.sh remove
sudo /etc/init.d/picopy.sh stop

echo "=> Removing picopy...\n"
sudo rm -rf /usr/local/bin/picopy.py 
sudo rm -rf /etc/init.d/picopy.sh 

echo "picopy uninstalled.\n"