FROM python:3.8-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libmagic1 \
    file \
 && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

CMD ["python", "app.py"]