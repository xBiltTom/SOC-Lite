FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY simulator.py .
USER nobody
CMD ["python", "simulator.py"]
