# syntax=docker/dockerfile:1
#
# Session TUI - Linux in Docker. Two uses:
#
#   1) run the app in a container (default target):
#        docker build -t session-tui .
#        docker run -it --rm -v session-tui-data:/data session-tui
#
#   2) build the standalone binary, without Python on the host:
#        docker build --target binary --output dist .
#      -> dist/session-tui  (built on Debian 11 / glibc 2.31, so it runs on
#         most distributions from 2020 on)

ARG PYTHON_VERSION=3.12

# --- standalone binary ---------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bullseye AS build
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY requirements.txt requirements-build.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check \
        -r requirements.txt -r requirements-build.txt
COPY . .
RUN python selftest.py \
 && python build_exe.py

FROM scratch AS binary
COPY --from=build /src/dist/session-tui /

# --- the app in a container (default) ------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color \
    COLORTERM=truecolor \
    XDG_DATA_HOME=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
COPY . .
RUN python selftest.py \
 && useradd --create-home --uid 1000 session \
 && mkdir -p /data \
 && chown session:session /data
USER session
# the account lives here (/data/session-tui/profile): keep it in a volume
VOLUME ["/data"]
ENTRYPOINT ["python", "/app/main.py"]
