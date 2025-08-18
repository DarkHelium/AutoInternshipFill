FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# 1) VNC desktop (+ a lightweight WM) + noVNC + websockify
RUN apt-get update && apt-get install -y --no-install-recommends \
    tigervnc-standalone-server xfce4 xfce4-terminal xdotool \
    dbus-x11 at-spi2-core \
    python3-websockify wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# noVNC
RUN mkdir -p /opt/novnc && \
    wget -qO- https://github.com/novnc/noVNC/archive/refs/heads/master.tar.gz | tar xz --strip 1 -C /opt/novnc && \
    ln -s /opt/novnc/utils/novnc_proxy /usr/local/bin/novnc_proxy

# 2) App user & workspace
RUN useradd -ms /bin/bash runner
USER runner
WORKDIR /home/runner

# 3) Install Python deps for automation API
USER root
RUN pip install fastapi uvicorn playwright httpx
RUN playwright install chromium

# 4) Entry script and automation server
COPY ./entry.sh /usr/local/bin/entry.sh
COPY ./automation_server.py /home/runner/automation_server.py
RUN chmod +x /usr/local/bin/entry.sh
USER runner

ENV DISPLAY=:20 \
    VNC_PORT=5901 \
    NOVNC_PORT=6080 \
    VNC_PASSWORD=secret

EXPOSE 6080 9001
ENTRYPOINT ["/usr/local/bin/entry.sh"]
