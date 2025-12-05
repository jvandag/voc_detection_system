#!/usr/bin/env bash
# Assuming python3 is installed
sudo apt-get install python3-pip
python3 -m venv ./.venv
source .venv/bin/activate
# pip install -r requirements.txt
pip install .
sudo groupadd --system gpio
sudo usermod -aG gpio "$USER"
echo 'KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpio.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

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