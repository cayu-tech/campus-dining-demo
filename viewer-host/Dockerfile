FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
RUN apt-get update && apt-get install -y --no-install-recommends docker-cli ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY viewer-host/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY viewer-host/cayu-0.5.2-py3-none-any.whl /tmp/cayu-0.5.2-py3-none-any.whl
RUN python -m pip install --no-cache-dir --no-deps /tmp/cayu-0.5.2-py3-none-any.whl
COPY catalog-app /opt/catalog-app
RUN python -m pip install --no-cache-dir --no-deps /opt/catalog-app \
    && python -m pip check
LABEL dev.cayu.campus.runtime="c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b"
CMD ["sleep", "infinity"]
