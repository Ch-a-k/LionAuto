#!/bin/bash

# Initialize directories
mkdir -p /run/clamav /var/lib/clamav
chown -R clamav:clamav /run/clamav /var/lib/clamav

# First-time database download with retries
echo "Running initial freshclam download..."
max_retries=5
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if freshclam --config-file=/etc/clamav/freshclam.conf; then
        echo "Initial database download successful"
        break
    else
        retry_count=$((retry_count+1))
        echo "Retry $retry_count of $max_retries..."
        sleep 10
    fi
done

if [ $retry_count -eq $max_retries ]; then
    echo "Warning: Failed to download initial database after $max_retries attempts"
fi

# Start services
echo "Starting ClamAV services..."
freshclam -d --config-file=/etc/clamav/freshclam.conf &
clamd --foreground &
wait -n
exit $?