#!/usr/bin/env bash
set -euo pipefail

cd /home/jeremiah/voc_detection_system/raspberry_pi_src

# Comment block out if you don't want to use tailscale
# echo "Setting up Tailscale VPN..."
# curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
# curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
# sudo apt-get update -y
# sudo apt-get install tailscale -y
# sudo systemctl enable tailscaled
# sudo systemctl start tailscaled
# sudo tailscale up # comment out if you don't want to use tailscale

sudo apt-get install tmux -y

sudo apt-get install python3-pip -y
python3 -m venv ./.venv
source .venv/bin/activate
# pip install -r requirements.txt 
pip install . 
sudo usermod -aG adm $USER
sudo usermod -a -G dialout "$USER"
sudo groupadd --system gpio
sudo usermod -aG gpio "$USER"

echo 'KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpio.rules
sudo udevadm control --reload --reload-rules && sudo udevadm trigger

echo "Setting up pigpio for hardware PWM..."

# Ensure we're root (drop 'sudo' inside the script)
if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: This script must be run as root. Try: sudo $0"
  exit 1
fi

# Install pigpio and Python bindings
apt-get update
apt-get install -y pigpio python3-pigpio

# Enable and start pigpiod so it's always running
sudo systemctl enable pigpiod
sudo systemctl start pigpiod


echo "pigpio setup complete. You can now use LEDBreather without sudo."


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
