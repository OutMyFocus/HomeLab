# The MTG scanner web app as a Docker image, for a home server (Unraid, Synology, any Docker
# host). The server has no camera or sorter hardware: you scan with your phone's or
# computer's camera from the Scan page, or upload photos. Data (card database, collection,
# settings) lives in /data; mount a folder there so it survives updates.
#
#   docker compose up -d                      # from this folder (see docker-compose.yml)
#   open http://<server>:5000
#
# Setting it up on Unraid, with the https address a phone camera needs: deploy/UNRAID.md.
FROM python:3.12-slim

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

COPY . .

VOLUME /data
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)" || exit 1

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
