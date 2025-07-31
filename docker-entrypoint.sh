#!/bin/bash
set -e

export USER=ubuntu
export HOME=/home/ubuntu
export XDG_RUNTIME_DIR=/run/user/$(id -u "$USER")

mkdir -p "$XDG_RUNTIME_DIR"
chown "$USER:$USER" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start dbus session for the user and log to a file for debugging
su - "$USER" -c "dbus-daemon --session --address=unix:path=$XDG_RUNTIME_DIR/bus --nofork" &

# Wait for D-Bus socket to exist
timeout=10
while [ ! -e "$XDG_RUNTIME_DIR/bus" ] && [ "$timeout" -gt 0 ]; do
    sleep 0.2
    timeout=$((timeout - 1))
done

# Final sanity check
if [ ! -e "$XDG_RUNTIME_DIR/bus" ]; then
    echo "D-Bus session did not start successfully"
    exit 1
fi

# Start SSH in foreground
exec /usr/sbin/sshd -D
# service ssh start
# bash
