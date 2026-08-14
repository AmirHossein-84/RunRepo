"""Safe environment variable value generation for local secrets and service URLs."""

import secrets
from typing import Any
from runrepo.env.models import EnvClassification, EnvRequirement


class EnvGenerator:
    """Generates safe local development values, database URLs, and random secrets."""

    @classmethod
    def generate_secret(cls, length: int = 32) -> str:
        """Generate a cryptographically secure URL-safe secret token."""
        return secrets.token_urlsafe(length)

    @classmethod
    def generate_postgres_url(
        cls,
        user: str = "postgres",
        password: str = "postgres",
        host: str = "localhost",
        port: int = 5432,
        db_name: str = "app_dev",
    ) -> str:
        """Construct a standardized local PostgreSQL connection URL."""
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    @classmethod
    def generate_redis_url(
        cls,
        host: str = "localhost",
        port: int = 6379,
    ) -> str:
        """Construct a standardized local Redis connection URL."""
        return f"redis://{host}:{port}"

    @classmethod
    def generate_value(
        cls,
        requirement: EnvRequirement,
        postgres_config: Any | None = None,
        redis_config: Any | None = None,
    ) -> str | None:
        """Generate a safe local value for an environment requirement.
        
        Never generates values for external third-party cloud services.
        """
        # Strictly reject external 3rd-party services
        if requirement.classification == EnvClassification.EXTERNAL_SERVICE:
            return None

        upper = requirement.name.upper()

        # 1. Database connection variables
        if upper in ("DATABASE_URL", "POSTGRES_URL"):
            if postgres_config:
                return cls.generate_postgres_url(
                    user=postgres_config.username,
                    password=postgres_config.password,
                    host="localhost",
                    port=postgres_config.host_port,
                    db_name=postgres_config.database_name,
                )
            return cls.generate_postgres_url()

        if upper == "POSTGRES_DB":
            return postgres_config.database_name if postgres_config else "app_dev"
        if upper == "POSTGRES_USER":
            return postgres_config.username if postgres_config else "postgres"
        if upper == "POSTGRES_PASSWORD":
            return postgres_config.password if postgres_config else "postgres"
        if upper == "POSTGRES_PORT":
            return str(postgres_config.host_port) if postgres_config else "5432"

        # 2. Redis connection variables
        if upper == "REDIS_URL":
            if redis_config:
                return cls.generate_redis_url(port=redis_config.host_port)
            return cls.generate_redis_url()
        if upper == "REDIS_PORT":
            return str(redis_config.host_port) if redis_config else "6379"
        if upper == "REDIS_HOST":
            return "localhost"

        # 3. Auto-generatable local secrets
        if requirement.classification == EnvClassification.AUTO_GENERATABLE:
            return cls.generate_secret(32)

        # 4. Local defaults
        if requirement.classification == EnvClassification.LOCAL_DEFAULT:
            if requirement.default_value:
                return requirement.default_value
            if upper == "PORT":
                return "3000"
            if upper == "HOST":
                return "localhost"
            if upper == "NODE_ENV":
                return "development"
            if upper in ("DEBUG", "ENVIRONMENT", "APP_ENV"):
                return "development" if upper != "DEBUG" else "True"

        # 5. User-required variables with example default
        if requirement.default_value:
            return requirement.default_value

        return None
