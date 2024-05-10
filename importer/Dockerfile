FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir templates

COPY templates/* templates/

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
