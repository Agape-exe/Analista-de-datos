import os

import uvicorn

from app.shared.adapters.observability.logging import configure_logging
from app.shared.config.settings import load_settings


def main() -> None:
    settings = load_settings()
    configure_logging()
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0" if settings.deployment.environment == "production" else "127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        workers=1,
    )


if __name__ == "__main__":
    main()
