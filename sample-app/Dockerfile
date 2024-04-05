# syntax=docker/dockerfile:1
FROM python:3.12-bookworm AS base
WORKDIR /tmp
COPY ./pyproject.toml .
RUN pip install .

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
RUN useradd -m nonroot
USER nonroot
COPY --from=base /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=base /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY ./src .
ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--log-config", "logger/logging_override.ini"]
