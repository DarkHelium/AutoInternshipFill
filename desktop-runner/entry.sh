#!/usr/bin/env bash
set -e

# 1) Start a VNC-backed X server (Xvnc) with a desktop session
mkdir -p ~/.vnc

# Initialize D-Bus session
eval `dbus-launch --sh-syntax`
export DBUS_SESSION_BUS_ADDRESS

# start Xvnc without auth (simpler for development)
Xtigervnc $DISPLAY -geometry 1440x900 -depth 24 -rfbport $VNC_PORT -SecurityTypes None &

# tiny wait for Xvnc to boot
sleep 2

# start a lightweight desktop with proper environment
DISPLAY=$DISPLAY startxfce4 &

# 2) Start noVNC (WebSocket proxy -> VNC server)
# will serve a web client at http://<host>:6080/vnc.html
novnc_proxy --vnc localhost:$VNC_PORT --listen 0.0.0.0:$NOVNC_PORT &
echo "noVNC on :$NOVNC_PORT → VNC on :$VNC_PORT"

# 3) Start automation API server
cd /home/runner
python3 automation_server.py &
echo "Automation API started on :9001"

# 4) Keep container alive; services running in background
tail -f /dev/null
