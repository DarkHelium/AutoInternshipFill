#!/usr/bin/env bash
set -e

# 1) Start a VNC-backed X server (Xvnc) with a desktop session
mkdir -p ~/.vnc
echo "$VNC_PASSWORD" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# start Xvnc
Xtigervnc $DISPLAY -geometry 1440x900 -depth 24 -rfbport $VNC_PORT -SecurityTypes VncAuth -rfbauth ~/.vnc/passwd &

# tiny wait for Xvnc to boot
sleep 1

# start a lightweight desktop
startxfce4 &

# 2) Start noVNC (WebSocket proxy -> VNC server)
# will serve a web client at http://<host>:6080/vnc.html
novnc_proxy --vnc localhost:$VNC_PORT --listen 0.0.0.0:$NOVNC_PORT &
echo "noVNC on :$NOVNC_PORT → VNC on :$VNC_PORT"

# 3) Keep container alive; Playwright will connect using DISPLAY
tail -f /dev/null
