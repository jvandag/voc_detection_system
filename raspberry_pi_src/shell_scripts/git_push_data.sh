#!/usr/bin/env bash

# Stage the current version of 
git add ~/voc_detection_system/raspberry_pi_src

# Commit with a timestamped message
git commit -m "chore: automatic data push @ $(date)"

# Push to git repo
git push