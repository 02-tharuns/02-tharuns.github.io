# Runtime image only needs backend/ — not content/. The BM25 corpus
# (data/corpus.json) is built by `python ingest.py` and committed, exactly
# like assets/corpus.js is for the static build; the container just loads
# it. That keeps the Docker build context to backend/ alone (matches
# Render's "root directory: backend" setup) instead of needing the whole
# repo as context to reach ../content.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY ingest.py .
COPY data/ data/
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
