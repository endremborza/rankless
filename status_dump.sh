#!/usr/bin/env bash

BE_SERVICE_NAME="rankless-backend.service"
CGROUP_PROCS="/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/${BE_SERVICE_NAME}/cgroup.procs"
CACHE_FILE="/tmp/status_cache.json"
INTERVAL=3

while true; do
    mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')     # in KB
    mem_avail=$(grep MemAvailable /proc/meminfo | awk '{print $2}') # in KB
    free_gb=$(awk -v a="$mem_avail" 'BEGIN {printf "%.2f", a/1024/1024}')
    free_pct=$(awk -v a="$mem_avail" -v t="$mem_total" 'BEGIN {printf "%.2f", (a/t)*100}')

    open_files=0
    if [[ -f "$CGROUP_PROCS" ]]; then
        while read -r pid; do
            if [[ -d "/proc/$pid/fd" ]]; then
                count=$(ls -1 "/proc/$pid/fd" 2>/dev/null | wc -l)
                open_files=$((open_files + count))
            fi
        done < "$CGROUP_PROCS"
    fi

    # Filesystem info (/dev/root)
    # Use POSIX df output (bytes, no human-readable)
    read fs_dev fs_size fs_used fs_avail fs_use fs_mount <<< \
        $(df -B1 --output=source,size,used,avail,pcent,target | grep "^/dev/root")
    fs_avail_bytes=$fs_avail
    fs_use_pct=${fs_use%\%}   # strip '%' sign

    timestamp=$(date +%s)
    tmpfile=$(mktemp)
    cat > "$tmpfile" <<EOF
{
  "memory_free_gb": $free_gb,
  "memory_free_pct": $free_pct,
  "open_files": $open_files,
  "fs_avail_bytes": $fs_avail_bytes,
  "fs_use_pct": $fs_use_pct,
  "timestamp": $timestamp
}
EOF
    mv "$tmpfile" "$CACHE_FILE"
    chmod 644 "$CACHE_FILE"
    sleep "$INTERVAL"
done
