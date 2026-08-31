FROM python:3.12-slim

WORKDIR /app

# build context is the repo root (see docker-compose.yml)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY datasets ./datasets

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
