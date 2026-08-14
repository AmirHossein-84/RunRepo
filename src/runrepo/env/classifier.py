"""Context-aware deterministic classification of environment variables."""

import re
from runrepo.env.models import EnvClassification

EXTERNAL_SERVICE_PATTERNS = [
    r"^OPENAI_",
    r"^ANTHROPIC_",
    r"^AWS_",
    r"^STRIPE_",
    r"^SENDGRID_",
    r"^SENTRY_",
    r"^GITHUB_TOKEN$",
    r"^SLACK_",
    r"^TWILIO_",
    r"^SUPABASE_ANON_KEY$",
    r"^SUPABASE_SERVICE_ROLE_KEY$",
    r"^CLERK_",
    r"^ALGOLIA_",
    r"^DATADOG_",
    r"^NEW_RELIC_",
    r"^MAILGUN_",
    r"^RESEND_API_KEY$",
]

_COMPILED_EXTERNAL_REGEX = re.compile(
    "|".join(EXTERNAL_SERVICE_PATTERNS),
    re.IGNORECASE,
)

AUTO_GENERATABLE_SECRET_PATTERNS = [
    r"^JWT_SECRET$",
    r"^SESSION_SECRET$",
    r"^APP_SECRET$",
    r"^SECRET_KEY$",
    r"^COOKIE_SECRET$",
    r"^NEXTAUTH_SECRET$",
    r"^AUTH_SECRET$",
    r"^ENCRYPTION_KEY$",
    r"^TOKEN_SECRET$",
]

_COMPILED_AUTO_SECRET_REGEX = re.compile(
    "|".join(AUTO_GENERATABLE_SECRET_PATTERNS),
    re.IGNORECASE,
)

LOCAL_DEFAULT_PATTERNS = [
    r"^PORT$",
    r"^HOST$",
    r"^NODE_ENV$",
    r"^ENVIRONMENT$",
    r"^DEBUG$",
    r"^LOG_LEVEL$",
    r"^ALLOWED_HOSTS$",
    r"^APP_ENV$",
    r"^BASE_URL$",
    r"^CORS_ORIGIN$",
    r"^API_PREFIX$",
    r"^TIMEZONE$",
]

_COMPILED_LOCAL_DEFAULT_REGEX = re.compile(
    "|".join(LOCAL_DEFAULT_PATTERNS),
    re.IGNORECASE,
)

DATABASE_VARIABLE_PATTERNS = [
    r"^DATABASE_URL$",
    r"^POSTGRES_URL$",
    r"^POSTGRES_DB$",
    r"^POSTGRES_PASSWORD$",
    r"^POSTGRES_USER$",
    r"^DB_NAME$",
    r"^DB_USER$",
    r"^DB_PASSWORD$",
    r"^DB_HOST$",
    r"^DB_PORT$",
]

_COMPILED_DATABASE_REGEX = re.compile(
    "|".join(DATABASE_VARIABLE_PATTERNS),
    re.IGNORECASE,
)

REDIS_VARIABLE_PATTERNS = [
    r"^REDIS_URL$",
    r"^REDIS_HOST$",
    r"^REDIS_PORT$",
    r"^REDIS_PASSWORD$",
]

_COMPILED_REDIS_REGEX = re.compile(
    "|".join(REDIS_VARIABLE_PATTERNS),
    re.IGNORECASE,
)


class EnvClassifier:
    """Classifies environment variables deterministically based on key patterns and project context."""

    @classmethod
    def classify(
        cls,
        name: str,
        has_local_postgres: bool = False,
        has_local_redis: bool = False,
        has_default: bool = False,
    ) -> EnvClassification:
        """Classify a variable taking into account local service availability."""
        upper_name = name.upper()

        # 1. External 3rd-party services (never auto-generate)
        if _COMPILED_EXTERNAL_REGEX.search(upper_name):
            return EnvClassification.EXTERNAL_SERVICE

        # 2. Local app secrets that can be securely generated
        if _COMPILED_AUTO_SECRET_REGEX.search(upper_name):
            return EnvClassification.AUTO_GENERATABLE

        # 3. Database connection & credentials
        if _COMPILED_DATABASE_REGEX.search(upper_name):
            if has_local_postgres:
                return EnvClassification.AUTO_GENERATABLE
            return EnvClassification.USER_REQUIRED

        # 4. Redis connection
        if _COMPILED_REDIS_REGEX.search(upper_name):
            if has_local_redis:
                return EnvClassification.AUTO_GENERATABLE
            return EnvClassification.LOCAL_DEFAULT

        # 5. Local defaults
        if _COMPILED_LOCAL_DEFAULT_REGEX.search(upper_name):
            return EnvClassification.LOCAL_DEFAULT

        if has_default:
            return EnvClassification.LOCAL_DEFAULT

        return EnvClassification.USER_REQUIRED
