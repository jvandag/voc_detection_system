#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update -y
sudo apt-get install python3-pip -y
python3 -m venv ./.venv
source .venv/bin/activate
# pip install -r requirements.txt 
pip install ../ 
sudo usermod -aG adm $USER
sudo usermod -a -G dialout "$USER"
sudo groupadd --system gpio
sudo usermod -aG gpio "$USER"

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

OVERLAY_LINE="dtoverlay=pwm-2chan,pin=13,func=4,pin2=19,func2=4"

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


echo 'KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpio.rules
sudo udevadm control --reload --reload-rules && sudo udevadm trigger

REAL_PWM_DIR=$(readlink -f /sys/class/pwm/pwmchip0)
sudo chgrp -R gpio "$REAL_PWM_DIR"
sudo chmod -R g+rw "$REAL_PWM_DIR"


# Configure cron job to automatically launch control system script
# Path to the script
TARGET_SCRIPT="$HOME/echo_test.sh"
# Log file for output
LOG_FILE="$HOME/echo_test.log"
# The cron line to install (runs at reboot, waits 10s for environment variables to be available)
CRON_ENTRY="@reboot sleep 10 && $TARGET_SCRIPT >> $LOG_FILE 2>&1"

# Safely get existing crontab (or empty) without failing under -e
existing=$(crontab -l 2>/dev/null || true)

# Check for existing crontab entry
if printf '%s
' "$existing" | grep -Fqx "$CRON_ENTRY"; then
  echo "Control system cron job already installed."
else
  # Append the cron entry without adding an extra blank line
  if [ -z "$existing" ]; then
    # no existing entries, install single line
    echo "$CRON_ENTRY" | crontab -
  else
    # preserve existing entries and add new one
    printf '%s
%s
' "$existing" "$CRON_ENTRY" | crontab -
  fi
  echo "Installed login cron job: $CRON_ENTRY"
fi

echo "Setup complete, restart required..."
