#!/bin/bash
set -e

PG_HBA=/etc/postgresql/15/main/pg_hba.conf

# Allow the rankless user to connect via TCP with password auth
if ! grep -q "^host.*rankless" "$PG_HBA"; then
    echo "host  rankless  rankless  127.0.0.1/32  md5" >> "$PG_HBA"
    echo "host  rankless  rankless  ::1/128        md5" >> "$PG_HBA"
fi

pg_ctlcluster 15 main start

until pg_isready -h 127.0.0.1 -p 5432 -U postgres -q; do
    echo "Waiting for PostgreSQL..."
    sleep 1
done

su postgres -c "psql -c \"CREATE USER rankless WITH PASSWORD 'rankless';\"" 2>/dev/null || true
su postgres -c "psql -c \"CREATE DATABASE rankless OWNER rankless;\"" 2>/dev/null || true

echo "=== Loading OA data into PostgreSQL (this takes a few minutes) ==="
cd /app
python3 sql-yardstick/create-schema-load-db.py

echo "=== Starting Flask server on 0.0.0.0:5000 ==="
exec python3 sql-yardstick/server.py
