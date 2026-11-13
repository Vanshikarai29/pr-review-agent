FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY reviewer ./reviewer
COPY evaluation ./evaluation

# Runs as a non-root user.
RUN useradd --create-home appuser
USER appuser

# Example: docker run --rm -e GEMINI_API_KEY=... -e GITHUB_TOKEN=... pr-review-agent --repo owner/name --pr 1
ENTRYPOINT ["python", "-m", "reviewer.main"]
