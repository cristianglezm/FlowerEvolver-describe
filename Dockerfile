# Stage 1: download model and dependency installation
FROM python:3.11-slim AS builder
RUN useradd --create-home fe
USER fe
WORKDIR /home/fe/app
ENV VIRTUAL_ENV=/home/fe/app/.venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --chown=fe:fe requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=fe:fe download_models.py .
RUN python download_models.py

# Stage 2: Final runtime stage
FROM python:3.11-slim
RUN useradd --create-home fe
#RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*
USER fe
WORKDIR /home/fe/app
RUN mkdir /home/fe/app/metrics
ENV prometheus_multiproc_dir=/home/fe/app/metrics
COPY --from=builder --chown=fe:fe /home/fe/app/.venv ./.venv
COPY --from=builder --chown=fe:fe /home/fe/app/models ./models
COPY --chown=fe:fe app ./app
COPY --chown=fe:fe .env .
COPY --chown=fe:fe docker/gunicorn_config.py .
ENV VIRTUAL_ENV=/home/fe/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn_config.py", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000"]
