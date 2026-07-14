# Espelho público do Docker Hub (evita 429 Too Many Requests em VPS)
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Estado do jogo persiste aqui — monte um volume do EasyPanel em /app/data
ENV DB_PATH=/app/data/ddr.db
VOLUME ["/app/data"]

CMD ["python", "main.py"]
