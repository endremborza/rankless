#!/bin/bash
# Wait for system to be ready
sleep 2
# Ensure the user slice is running
systemctl start user-1000.slice 2>/dev/null || true
# Start user systemd if not running
if ! pgrep -f "/usr/lib/systemd/systemd --user" > /dev/null; then
    sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 /usr/lib/systemd/systemd --user &
fi
