ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/docker_deterministic_acceptance.py /app/docker_deterministic_acceptance.py
COPY scripts/docker_local_llm_acceptance.py /app/docker_local_llm_acceptance.py

ENTRYPOINT ["python", "/app/docker_local_llm_acceptance.py"]
