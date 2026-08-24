#!/bin/bash
set -e

rsync -az --delete \
  --exclude='.env' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  -e "ssh -F /data/data/com.termux/files/home/.ssh/config" \
  /data/data/com.termux/files/home/Mimoru/ \
  mimoru-server:/root/Mimoru/
