ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/docker_provider_free_acceptance.py /app/docker_provider_free_acceptance.py

ENTRYPOINT ["python", "/app/docker_provider_free_acceptance.py"]
