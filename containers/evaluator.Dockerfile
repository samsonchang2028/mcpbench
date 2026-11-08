# No build/pull has run. Installs only locked wheels during an admitted build.
FROM docker.io/library/python:3.14.4-slim-bookworm@sha256:db5942d111df72110e7a67da3fc5159e83ac85cd24808b91bdc4769e166ed1b7
WORKDIR /app
COPY uv.lock /tmp/uv.lock
COPY containers/install_locked.py /tmp/install_locked.py
RUN python /tmp/install_locked.py && rm /tmp/uv.lock /tmp/install_locked.py /tmp/requirements.txt
COPY eval/ /app/eval/
COPY contracts/ /app/contracts/
COPY db/ /app/db/
USER 1000:1000
ENV HOME=/nonexistent TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "eval.runner"]
