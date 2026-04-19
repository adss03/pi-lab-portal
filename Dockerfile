FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG DJANGO_SECRET_KEY=build-placeholder
ARG POSTGRES_DB=placeholder
ARG POSTGRES_USER=placeholder
ARG POSTGRES_PASSWORD=placeholder
RUN DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY} \
    POSTGRES_DB=${POSTGRES_DB} \
    POSTGRES_USER=${POSTGRES_USER} \
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "portal.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1"]
