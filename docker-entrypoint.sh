#!/bin/bash
set -e

export USER=ubuntu
export HOME=/home/ubuntu
export XDG_RUNTIME_DIR=/run/user/$(id -u "$USER")
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

mkdir -p "$XDG_RUNTIME_DIR"
chown "$USER:$USER" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start dbus for user
su - "$USER" -c "dbus-daemon --session --address=unix:path=$XDG_RUNTIME_DIR/bus --nofork" &

# Wait for dbus to come up
for i in {1..10}; do
    [ -e "$XDG_RUNTIME_DIR/bus" ] && break
    sleep 0.2
done

# Start SSH in foreground
exec /usr/sbin/sshd -D
