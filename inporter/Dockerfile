# Verwenden des offiziellen Python 3.8-Images als Basis
FROM python:3.8-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieren des Flask-Skripts in den Container
COPY app.py /root/

# Port freigeben, der vom Flask-Server verwendet wird
EXPOSE 5000

# Befehl zum Starten der Anwendung, wenn der Container gestartet wird
CMD ["flask", "run", "--host=0.0.0.0"]
