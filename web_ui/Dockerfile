FROM python:3.12-slim

WORKDIR /app

# Install both packages so web_ui can import from mcp_server
COPY mcp_server /app/mcp_server
COPY web_ui /app/web_ui

RUN pip install --no-cache-dir ./mcp_server ./web_ui

EXPOSE 11489

CMD ["uvicorn", "web_ui.app.main:app", "--host", "0.0.0.0", "--port", "11489"]
