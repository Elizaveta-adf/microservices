FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py json_logger.py tracing.py ./

CMD ["python", "-u", "main.py"]