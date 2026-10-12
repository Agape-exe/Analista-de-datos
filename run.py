import uvicorn

from app.observability.logging import configure_logging

if __name__ == "__main__":
    configure_logging()
    uvicorn.run("app.api.main:app")
