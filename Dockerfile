# Rural Hospital AI Radiology Triage - Backend
# Python 3.9 for compatibility with torchxrayvision
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories for uploads and heatmaps
RUN mkdir -p uploads heatmaps static

EXPOSE 5000

# PORT can be overridden by Render/hosting
ENV PORT=5000
CMD ["python", "app.py"]
