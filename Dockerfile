FROM python:3.12-slim

WORKDIR /app
COPY backend/ ./backend/

# Jangan jalan sebagai root.
RUN useradd --create-home appuser
USER appuser

# Platform deploy (Render/Fly/dll) menyuntikkan PORT sendiri; lokal default 8000.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health', timeout=4)"

CMD ["python3", "backend/main.py"]
