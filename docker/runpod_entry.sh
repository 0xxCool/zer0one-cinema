#!/bin/bash
# RunPod entry script: sets up SSH from PUBLIC_KEY env var, then runs sshd in
# the foreground so the container stays alive and RunPod's control plane can
# route port 22 to the pod's public IP.
#
# Design: sshd -D keeps this PID 1, and any command passed to `docker exec`
# (or `runpod exec`) reaches the running container normally.
set -e

mkdir -p /root/.ssh /var/run/sshd
chmod 700 /root/.ssh

if [[ -n "${PUBLIC_KEY:-}" ]]; then
  echo "${PUBLIC_KEY}" > /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
  echo "runpod-entry: authorized_keys installed for root"
else
  echo "runpod-entry: WARN — no PUBLIC_KEY env var; SSH access will fail"
fi

# generate host keys if missing (first boot)
ssh-keygen -A

echo "runpod-entry: starting sshd -D on port 22"
exec /usr/sbin/sshd -D -e
