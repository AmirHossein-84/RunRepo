"""Unit tests for DatabaseDetector."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detectors.database import DatabaseDetector
from runrepo.models import DatabaseType


def test_database_detector_prisma_postgresql(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "prisma/schema.prisma": """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}
""",
        }
    )

    detector = DatabaseDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert len(result.databases) == 1
    assert result.databases[0].name == DatabaseType.POSTGRESQL
    assert result.databases[0].orm == "prisma"
    assert result.databases[0].connection_var == "DATABASE_URL"


def test_database_detector_alembic_with_url(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "alembic.ini": "[alembic]\nscript_location = alembic\nsqlalchemy.url = postgresql://user:pass@localhost/db\n",
            "alembic/env.py": "# alembic env\n",
        }
    )

    detector = DatabaseDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert len(result.databases) == 1
    assert result.databases[0].name == DatabaseType.POSTGRESQL
    assert result.databases[0].orm == "alembic"


def test_database_detector_alembic_unknown_without_spec(create_fixture_repo):
    repo = create_fixture_repo(
        {
            "alembic.ini": "[alembic]\nscript_location = alembic\n",
            "alembic/env.py": "# alembic env\n",
        }
    )

    detector = DatabaseDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    assert len(result.databases) == 1
    assert result.databases[0].name == DatabaseType.UNKNOWN
    assert result.databases[0].orm == "alembic"


def test_database_detector_compose_mysql_db_service(create_fixture_repo):
    # Verify service named 'db' with mysql image is classified as MySQL, NOT PostgreSQL
    repo = create_fixture_repo(
        {
            "compose.yaml": """
services:
  db:
    image: mysql:8.0
  cache:
    image: redis:alpine
""",
        }
    )

    detector = DatabaseDetector()
    context = ScanContext(repo)
    result = detector.detect(context)

    db_names = {d.name for d in result.databases}
    assert DatabaseType.MYSQL in db_names
    assert DatabaseType.REDIS in db_names
    assert DatabaseType.POSTGRESQL not in db_names

    svc_names = {s.name for s in result.services}
    assert "redis" in svc_names
