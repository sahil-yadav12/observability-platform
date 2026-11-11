FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py loadgen.py ./
EXPOSE 8000
# Single worker + threads so the in-process Prometheus registry stays consistent.
CMD ["gunicorn", "-w", "1", "--threads", "32", "-b", "0.0.0.0:8000", "app:app"]
