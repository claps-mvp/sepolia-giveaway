FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY .env /app/

COPY . /app/

CMD ["gunicorn", "--bind", ":8000", "--workers", "3", "app.wsgi:application"]
