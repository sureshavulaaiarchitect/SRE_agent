from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Literal, Optional, List
import sys

class Settings(BaseSettings):
    # Multi-Cluster Config
    CLUSTERS: List[str] = ["local-dev-cluster", "staging-cluster", "production-cluster"]
    CURRENT_CLUSTER_ID: str = "local-dev-cluster"
    CONTROL_PLANE_URL: Optional[str] = None

    # DB Config
    DATABASE_URL: str = "postgresql+asyncpg://k8s-agent:password@postgres:5432/sre_agent"

    # AI Config
    AI_BACKEND: Literal["ollama", "openai", "anthropic"] = "ollama"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "sre-agent:latest"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Ollama Options
    OLLAMA_OPTIONS: dict = {"temperature": 0.1, "num_predict": 1024}
    OLLAMA_HEALTH_CHECK_URL: str = "http://host.docker.internal:11434/api/tags"
    # Inner Ollama HTTP timeout (seconds); outer asyncio.wait_for uses AI_REQUEST_TIMEOUT
    OLLAMA_TIMEOUT: float = 30.0
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60

    # Paths
    PATTERNS_PATH: str = "knowledge/incident_patterns.json"
    PLAYBOOKS_PATH: str = "playbooks/"

    # Notifications
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Notifications - Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    ALERT_FROM_EMAIL: str = "sre-agent@yourdomain.com"
    ALERT_TO_EMAILS: str = ""

    # Notifications - PagerDuty
    PAGERDUTY_API_KEY: Optional[str] = None
    PAGERDUTY_SERVICE_ID: Optional[str] = None
    PAGERDUTY_FROM_EMAIL: str = "sre-agent@yourdomain.com"

    # Auth — JWT
    JWT_SECRET: str = "change-me-in-production"
    WS_AUTH_TOKEN: str = "demo-token"
    DEV_MODE: bool = True

    # Auth — API credentials (set via env vars in production)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: Optional[str] = None  # Must be set when DEV_MODE=False

    # CORS — restrict in production (comma-separated or JSON list via env)
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Connection Limits
    WS_GLOBAL_LIMIT: int = 100
    WS_IP_LIMIT: int = 5

    # Remediation Limits
    REMEDIATION_MAX_PER_POD: int = 3
    REMEDIATION_WINDOW: int = 300  # 5 minutes

    # AI Hardening — outer timeout must exceed OLLAMA_TIMEOUT
    AI_REQUEST_TIMEOUT: float = 35.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Reject dangerous defaults when DEV_MODE is off."""
        if not self.DEV_MODE:
            errors = []
            if self.JWT_SECRET == "change-me-in-production":
                errors.append("JWT_SECRET must be overridden (current value is the insecure default)")
            if self.WS_AUTH_TOKEN == "demo-token":
                errors.append("WS_AUTH_TOKEN must be overridden (current value is the insecure default)")
            if self.ADMIN_PASSWORD is None:
                errors.append("ADMIN_PASSWORD must be set when DEV_MODE=False")
            if errors:
                msg = "Production safety check failed:\n  " + "\n  ".join(errors)
                print(f"FATAL: {msg}", file=sys.stderr)
                sys.exit(1)
        if self.AI_REQUEST_TIMEOUT <= self.OLLAMA_TIMEOUT:
            # Outer timeout must be larger so Ollama's inner timeout fires first
            self.AI_REQUEST_TIMEOUT = self.OLLAMA_TIMEOUT + 5.0
        return self

settings = Settings()

