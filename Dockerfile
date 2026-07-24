FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot.py .
COPY reports.json . 2>/dev/null || true

# Expose port
EXPOSE 8080

# Run bot
CMD ["python", "bot.py"]
