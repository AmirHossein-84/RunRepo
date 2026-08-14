"""Unit tests for EnvironmentDetector."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.env import EnvironmentDetector
from runrepo.models import EnvVarCategory


def test_env_detector_parsing(create_fixture_repo):
    repo = create_fixture_repo(
        {
            ".env.example": """
# Database connection
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb

# JWT Secret key
JWT_SECRET=xxx

# Server Port
PORT=3000

# Third-party service
STRIPE_SECRET_KEY=sk_test_12345
""",
        }
    )

    detector = EnvironmentDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    env_map = {e.name: e for e in result.environment_variables}
    assert "DATABASE_URL" in env_map
    assert env_map["DATABASE_URL"].category == EnvVarCategory.DATABASE
    assert env_map["DATABASE_URL"].description == "Database connection"

    assert "JWT_SECRET" in env_map
    assert env_map["JWT_SECRET"].category == EnvVarCategory.SECRET
    assert env_map["JWT_SECRET"].is_required is True

    assert "PORT" in env_map
    assert env_map["PORT"].category == EnvVarCategory.LOCAL_DEFAULT
    assert env_map["PORT"].default_value == "3000"

    assert "STRIPE_SECRET_KEY" in env_map
    assert env_map["STRIPE_SECRET_KEY"].category == EnvVarCategory.EXTERNAL_SERVICE
