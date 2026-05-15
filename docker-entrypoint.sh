#!/bin/sh
set -e
# Fix ownership of the data volume. When an existing volume was created while
# the container ran as root, the mounted directory is root-owned and appuser
# cannot write to it. This runs as root before dropping privileges.
chown -R appuser:appgroup /app/data
exec gosu appuser "$@"
