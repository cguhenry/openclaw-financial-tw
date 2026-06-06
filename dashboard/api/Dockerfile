FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DASHBOARD_API_HOST=0.0.0.0 \
    DASHBOARD_API_PORT=9180

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY dashboard/api/requirements.txt ./dashboard-api-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r dashboard-api-requirements.txt

COPY mcp ./mcp
COPY dashboard/api ./dashboard/api

EXPOSE 9180

CMD ["python", "-m", "uvicorn", "dashboard.api.app.main:app", "--host", "0.0.0.0", "--port", "9180"]
