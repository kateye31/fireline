#!/usr/bin/env bash
# Make the Jetson join ONLY the phone hotspot, automatically at boot (before anyone logs in),
# retrying forever, and stop every other saved Wi-Fi network from auto-connecting.
#   sudo bash hotspot_only.sh "Hotspot Name" "hotspot-password"
# Run it from the Jetson's own keyboard if you can: the Wi-Fi reconnects, so an SSH session may drop.
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: sudo bash $0 \"Hotspot Name\" \"password\""; exit 1; }
SSID="$1"; PASS="$2"; NAME="fireline-hotspot"
IFACE="$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')"
[ -n "$IFACE" ] || { echo "no Wi-Fi device found"; exit 1; }

nmcli connection delete "$NAME" >/dev/null 2>&1 || true
nmcli connection add type wifi con-name "$NAME" ifname "$IFACE" ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" \
    connection.autoconnect yes connection.autoconnect-priority 100 connection.autoconnect-retries 0 \
    connection.permissions ""

# Every other saved Wi-Fi network: keep it saved, but never join it automatically.
nmcli -t -f NAME,TYPE connection show | while IFS=: read -r con type; do
    if [ "$type" = "802-11-wireless" ] && [ "$con" != "$NAME" ]; then
        nmcli connection modify "$con" connection.autoconnect no
        echo "auto-connect off: $con"
    fi
done

nmcli connection up "$NAME"
echo "Done. Saved Wi-Fi networks:"
nmcli -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show
