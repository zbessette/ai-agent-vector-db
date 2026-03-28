import httpx


class OllamaEmbedder:
    def __init__(self, host: str, port: int, model: str):
        self.url = f"http://{host}:{port}/api/embed"
        self.model = model

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            self.url,
            json={"model": self.model, "input": text},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]
