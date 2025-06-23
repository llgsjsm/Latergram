FROM python:3.8-alpine

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

CMD ["python", "app.py"]