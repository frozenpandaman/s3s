FROM --platform=linux/amd64 python:3.10-slim

# Set pip to have no saved cache
ENV PIP_NO_CACHE_DIR=false \
    POETRY_VIRTUALENVS_CREATE=false

ENTRYPOINT ["python", "./s3s.py"]

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ARG git_sha="development"
ENV GIT_SHA=$git_sha

COPY . .