#!/usr/bin/env bash
# # This script should be set to run when the PI starts to automate the control system


AUTO_PUSH_DATA=TRUE # TRUE or FALSE

# check if system control script is already running, if running exit
if tmux has-session -t ctrl_sys; then
  echo "Script is already running in a tmux session. Exiting."
  exit 1
fi

tailscale up --operator=$USER


# Start a new tmux session named '0' and start the first command
tmux new-session -d -s 0 -n ctrl_sys

tmux send-keys -t 0 'cd ~/voc_detection_system/raspberry_pi_src' C-m

# Send keys to tmux session for activating the virtual environment and starting the Discord bot
# Uncomment following line if run.sh is outside of directory
# tmux send-keys -t 0 'cd ephemeris-generator' C-m
tmux send-keys -t 0 'echo "Activating virtual environment..."' C-m
tmux send-keys -t 0 'source .venv/bin/activate' C-m
tmux send-keys -t 0 'echo "Starting Control Script..."' C-m
tmux send-keys -t 0 'python3 main.py' C-m


# if enabled, run a cron job in the new terminal pane to push the gathered data to the git repo twice a day
if [ "$AUTO_PUSH_DATA" = "TRUE" ]; then
  echo "Script is already running in a tmux session. Exiting."
  tmux split-window -h -t 0
  tmux send-keys -t 0 'cd ~/voc_detection_system/raspberry_pi_src/shell_scripts' C-m
  tmux send-keys -t 0 ' 0 0,12 * * * git_push_data.sh >> git_auto_push.log 2>&1' C-m
fi
