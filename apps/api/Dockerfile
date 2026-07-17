FROM python:3.12-alpine3.24

ARG TARGETARCH
ARG TECTONIC_VERSION=0.16.9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    XDG_CACHE_HOME=/opt/tectonic-cache \
    PORT=8000 \
    TECTONIC_BINARY=/usr/local/bin/tectonic \
    TECTONIC_ONLY_CACHED=true

RUN apk add --no-cache ca-certificates libstdc++ \
    && apk add --no-cache --virtual .download-deps curl \
    && case "${TARGETARCH}" in \
        amd64) \
            TECTONIC_ARCH="x86_64-unknown-linux-musl"; \
            TECTONIC_SHA256="60b13a0826ae7ad9ce34b4a2df06bff2cfcfa6dda8a915477c0cbb84e1a4a902" ;; \
        arm64) \
            TECTONIC_ARCH="aarch64-unknown-linux-musl"; \
            TECTONIC_SHA256="f9aa39017dbd51f111fdb93dda222178cbe51c8193508fc567b523cc74fff9c1" ;; \
        *) echo "Unsupported container architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && TECTONIC_ARCHIVE="tectonic-${TECTONIC_VERSION}-${TECTONIC_ARCH}.tar.gz" \
    && curl --fail --location --retry 3 \
        "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/${TECTONIC_ARCHIVE}" \
        --output "/tmp/${TECTONIC_ARCHIVE}" \
    && echo "${TECTONIC_SHA256}  /tmp/${TECTONIC_ARCHIVE}" | sha256sum -c - \
    && tar --extract --gzip --file "/tmp/${TECTONIC_ARCHIVE}" --directory /usr/local/bin tectonic \
    && chmod 0755 /usr/local/bin/tectonic \
    && rm "/tmp/${TECTONIC_ARCHIVE}" \
    && apk del .download-deps

COPY docker/tectonic-warmup.tex /tmp/tectonic-warmup.tex

RUN mkdir -p /tmp/tectonic-warmup "${XDG_CACHE_HOME}" \
    && tectonic --untrusted --outdir /tmp/tectonic-warmup /tmp/tectonic-warmup.tex \
    && rm -rf /tmp/tectonic-warmup /tmp/tectonic-warmup.tex

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --upgrade pip==26.1.2 \
    && pip install . \
    && addgroup -S app \
    && adduser -S -G app -h /home/app app \
    && chown -R app:app /app "${XDG_CACHE_HOME}"

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/v1/health/', timeout=4)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips='*'"]
