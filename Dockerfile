FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python init_db.py
EXPOSE 5001
ENV PORT=5001
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
CMD ["python", "app.py"]
