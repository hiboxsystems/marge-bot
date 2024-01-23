# syntax=docker/dockerfile:1

FROM python:3.10-slim@sha256:9956522e7eafd57e3e7bb4b102d56f02882924019867cd2036c1a7c3ee56b174 AS builder

ARG POETRY_VERSION=1.5.1
RUN pip -V
# hadolint ignore=DL3042
RUN --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip \
    pip install --no-compile poetry==$POETRY_VERSION

WORKDIR /app

COPY marge/ ./marge/
RUN --mount=type=bind,source=poetry.lock,target=poetry.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=bind,source=pylintrc,target=pylintrc \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip \
    poetry export -o requirements.txt \
    && pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt \
    && poetry build --quiet --no-ansi --no-interaction --format=sdist

FROM python:3.10-slim@sha256:9956522e7eafd57e3e7bb4b102d56f02882924019867cd2036c1a7c3ee56b174 AS runtime

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update -q \
    && apt-get install -yq --no-install-recommends \
    git=1:2.39.2-1.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/log/*

RUN groupadd -g 1000 unprivileged && \
    useradd --create-home -r -u 1000 -g unprivileged unprivileged

USER unprivileged
WORKDIR /app

ENV PATH="/home/unprivileged/.local/bin:${PATH}"

# hadolint ignore=DL3042
RUN --mount=type=cache,sharing=locked,uid=1000,gid=1000,id=pipcache,mode=0777,target=/home/unprivileged/.cache/pip \
    --mount=type=bind,from=builder,source=/app/wheels,target=/wheels \
    --mount=type=bind,from=builder,source=/app/dist,target=/dist \
    pip install --no-compile /wheels/* /dist/*

ENTRYPOINT ["marge"]
