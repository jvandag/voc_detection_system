#!/usr/bin/env bash
set -euo pipefail

echo "Configuring hardware PWM on GPIO13 (header pin 33)..."

# Must be run as root
if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: This script must be run as root. Try: sudo $0"
  exit 1
fi

# Find the correct config.txt
CONFIG_PATH=""
if [[ -f /boot/firmware/config.txt ]]; then
  CONFIG_PATH="/boot/firmware/config.txt"
elif [[ -f /boot/config.txt ]]; then
  CONFIG_PATH="/boot/config.txt"
else
  echo "ERROR: Could not find /boot/firmware/config.txt or /boot/config.txt"
  exit 1
fi

echo "Using config file: $CONFIG_PATH"

OVERLAY_LINE="dtoverlay=pwm,pin=13,func=4"

# Check if an overlay for pwm+pin=13 is already present
if grep -Eq 'dtoverlay=pwm.*pin=13' "$CONFIG_PATH"; then
  echo "PWM overlay for GPIO13 already present in $CONFIG_PATH. Skipping."
else
  echo "Adding PWM overlay for GPIO13 to $CONFIG_PATH..."
  {
    echo ""
    echo "# Enable hardware PWM on GPIO13 (header pin 33) for LED breather"
    echo "$OVERLAY_LINE"
  } >> "$CONFIG_PATH"
  echo "Overlay added."
fi

echo "Done configuring PWM. You must reboot for changes to take effect."
echo "Run: sudo reboot"
