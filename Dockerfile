FROM python:3.10-slim AS builder

ARG POETRY_VERSION=1.4.2
RUN pip -V
RUN pip install poetry==$POETRY_VERSION

WORKDIR /src

COPY pyproject.toml poetry.lock README.md pylintrc ./
COPY marge/ ./marge/
RUN poetry export -o requirements.txt && \
  poetry build


FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
  git-core build-essential \
  && \
  rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/requirements.txt /src/dist/marge-*.tar.gz /tmp/

RUN pip install --no-deps -r /tmp/requirements.txt && \
  pip install /tmp/marge-*.tar.gz

ENTRYPOINT ["marge"]
