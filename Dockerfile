FROM python:3.11-slim

WORKDIR /app

# patch binary for applying diffs (falls back to pure-Python if absent)
RUN apt-get update && apt-get install -y --no-install-recommends patch && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["orqis", "start", "--host", "0.0.0.0", "--port", "8000"]
