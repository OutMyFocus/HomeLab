# The MTG scanner web app as a Docker image, for a home server (Unraid, Synology, any Docker
# host) and for the sorter's Raspberry Pi 5. Data (card database, collection, settings)
# lives in /data; mount a folder there so it survives updates.
#
#   docker compose up -d                      # from this folder (see docker-compose.yml)
#   open http://<server>:5000
#
# Two flavours, picked by the platform it's built for (GitHub builds both, see
# .github/workflows/mtg-sorter-image.yml):
#   amd64  a server: no camera or sorter hardware. You scan with your phone's or computer's
#          camera from the Scan page, or upload photos. Setting it up on Unraid: deploy/UNRAID.md.
#   arm64  the Pi: Raspberry Pi OS's camera, GPIO and vcgencmd packages, so the Pi camera,
#          servo board, feeder and light bars work from inside the container. The Pi runs it
#          with deploy/mtg-sorter-docker.service (switch with: mtg docker on). See deploy/PI_DOCKER.md.

# Set by docker buildx to amd64 or arm64; picks the base below.
ARG TARGETARCH

# --- amd64: plain Python ----------------------------------------------------------------
FROM python:3.12-slim AS base-amd64

# --- arm64: Debian with the Raspberry Pi repository, like Raspberry Pi OS ---------------
# picamera2 and libcamera only come as Raspberry Pi OS packages (not from pip), so this
# flavour uses the system Python and a venv that can see them (--system-site-packages).
FROM debian:trixie-slim AS base-arm64
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
       | gpg --dearmor -o /usr/share/keyrings/raspberrypi.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/raspberrypi.gpg] http://archive.raspberrypi.com/debian trixie main" \
       > /etc/apt/sources.list.d/raspi.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip \
       python3-picamera2 python3-libcamera \
       python3-gpiozero python3-lgpio python3-rpi-lgpio \
       raspi-utils-core \
    && apt-get purge -y gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    LG_WD=/tmp

# --- the app, the same for both ---------------------------------------------------------
FROM base-${TARGETARCH}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MTG_DATA_DIR=/data \
    MTG_IN_DOCKER=1 \
    OPENCV_LOG_LEVEL=ERROR

WORKDIR /app

# The headless OpenCV build has no window code, so the image needs no X11 or OpenGL libraries.
COPY requirements.txt .
RUN sed -i 's/^opencv-python>/opencv-python-headless>/' requirements.txt \
    && pip install -r requirements.txt

# Which commit of main the image was built from (shown on the Maintenance page). Set after
# the packages so a new commit doesn't make them install again.
ARG MTG_VERSION=""
ENV MTG_VERSION=${MTG_VERSION}

COPY . .

VOLUME /data
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)" || exit 1

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
