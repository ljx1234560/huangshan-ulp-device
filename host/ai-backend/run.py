"""Run the product-owned VelaPet chat backend."""

from pathlib import Path
import os

from dotenv import load_dotenv
import uvicorn


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    load_dotenv(root / ".env")

    from velapet_backend.config import Settings

    settings = Settings.from_env()
    settings.validate_bind()
    uvicorn.run(
        "velapet_backend.main:app",
        host=settings.host,
        port=settings.port,
        workers=1,
    )
