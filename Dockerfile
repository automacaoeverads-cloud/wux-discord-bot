FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro (cache de build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# É um worker (sem porta HTTP) — só roda o bot.
# -u = saída sem buffer, pra os logs aparecerem no EasyPanel.
CMD ["python", "-u", "bot.py"]
