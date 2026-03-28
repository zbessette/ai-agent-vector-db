FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 11488

ENTRYPOINT ["python", "server.py"]
CMD ["--sse"]
