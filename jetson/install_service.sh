#!/usr/bin/env bash
# One-time setup: start the field unit automatically on every boot.
#   cd ~/jetsonyay/jetson && bash install_service.sh
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(cd .. && pwd)"

[ -f yolov8s.engine ] || echo "warning: no yolov8s.engine here yet; set MODEL=yolov8s.pt in /etc/fireline-unit.env or export the engine first"

sudo docker build -t fireline-unit .
[ -f /etc/fireline-unit.env ] || sudo cp fireline-unit.env.example /etc/fireline-unit.env
sed "s#__REPO__#$REPO#" fireline-unit.service | sudo tee /etc/systemd/system/fireline-unit.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable docker mosquitto ssh
sudo systemctl enable --now fireline-unit

echo
echo "Installed. The unit now starts on every boot."
echo "  settings: sudo nano /etc/fireline-unit.env, then sudo systemctl restart fireline-unit"
echo "  logs:     journalctl -u fireline-unit -f"
echo "  stop:     sudo systemctl stop fireline-unit   (disable on boot: sudo systemctl disable fireline-unit)"
