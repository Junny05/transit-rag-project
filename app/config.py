import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    MTA_API_KEY: str = os.getenv("MTA_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    MTA_FEED_URL: str = (
        "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
    )
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # How often the background job re-pulls the GTFS-RT feed (seconds)
    FEED_REFRESH_INTERVAL_SECONDS: int = int(os.getenv("FEED_REFRESH_INTERVAL_SECONDS", "60"))

    # Network timeouts / retry behavior
    HTTP_TIMEOUT_SECONDS: float = 10.0
    MAX_RETRIES: int = 3

    def validate(self) -> None:
        missing = [
            name
            for name, val in [
                ("MTA_API_KEY", self.MTA_API_KEY),
                ("GEMINI_API_KEY", self.GEMINI_API_KEY),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


settings = Settings()
