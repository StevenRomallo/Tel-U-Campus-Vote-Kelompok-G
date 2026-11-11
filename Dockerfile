FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 DATA_DIR=/var/lib/backend_data
WORKDIR /app
RUN addgroup -g 10001 campus && adduser -D -u 10001 -G campus campus \
    && mkdir -p /var/lib/backend_data && chown campus:campus /var/lib/backend_data
COPY --chown=campus:campus app.py config.json ./
USER campus
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "app.py"]
