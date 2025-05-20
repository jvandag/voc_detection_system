#!/usr/bin/env bash
# # This script should be set to run when the PI starts to automate the control system


AUTO_PUSH_DATA=TRUE # TRUE or FALSE
CRON_LINE='0 0,12 * * * ~/voc_detection_system/raspberry_pi_src/shell_scripts/git_push_data.sh >> ~/voc_detection_system/raspberry_pi_src/shell_scripts/git_auto_push.log 2>&1'

# if enabled, run a cron job in the new terminal pane to push the gathered data to the git repo twice a day
if [ "$AUTO_PUSH_DATA" = "TRUE" ]; then
  # If enabled, ensure the tmux pane is running and the cron job is installed
  tmux split-window -h -t ctrl_sys || true
  tmux send-keys -t ctrl_sys 'cd ~/voc_detection_system/raspberry_pi_src/shell_scripts' C-m

  # Install cron job if missing
  if crontab -l 2>/dev/null | grep -Fqx "$CRON_LINE"; then
    echo "Cron job already installed; skipping."
  else
    ( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
    echo "Installed new cron job: $CRON_LINE"
  fi
else
  # If disabled, remove the cron job if it exists
  if crontab -l 2>/dev/null | grep -Fqx "$CRON_LINE"; then
    # Filter out the matching line and reinstall crontab
    crontab -l 2>/dev/null | grep -Fvx "$CRON_LINE" | crontab -
    echo "Removed cron job: $CRON_LINE"
  else
    echo "Cron job not present; nothing to remove."
  fi
fi


# check if system control script is already running, if running exit
if tmux has-session -t ctrl_sys; then
  echo "Script is already running in a tmux session. Exiting."
  exit 1
fi

tailscale up --operator=$USER


# Start a new tmux session named '0' and start the first command
tmux new-session -d -s ctrl_sys -n ctrl_sys

tmux send-keys -t ctrl_sys 'cd ~/voc_detection_system/raspberry_pi_src' C-m

# Send keys to tmux session for activating the virtual environment and starting the Discord bot
# Uncomment following line if run.sh is outside of directory
# tmux send-keys -t 0 'cd ephemeris-generator' C-m
tmux send-keys -t ctrl_sys 'echo "Activating virtual environment..."' C-m
tmux send-keys -t ctrl_sys 'source .venv/bin/activate' C-m
tmux send-keys -t ctrl_sys 'echo "Starting Control Script..."' C-m
tmux send-keys -t ctrl_sys 'python3 main.py' C-m
