"""Unit tests for safe local environment value generation."""

from runrepo.env.generator import EnvGenerator
from runrepo.env.models import EnvClassification, EnvRequirement
from runrepo.services.models import PostgresConfig, RedisConfig


def test_generate_secret():
    s1 = EnvGenerator.generate_secret(32)
    s2 = EnvGenerator.generate_secret(32)
    assert len(s1) > 20
    assert len(s2) > 20
    assert s1 != s2


def test_generate_postgres_and_redis_urls():
    pg_url = EnvGenerator.generate_postgres_url(port=5433, db_name="test_dev")
    assert pg_url == "postgresql://postgres:postgres@localhost:5433/test_dev"

    redis_url = EnvGenerator.generate_redis_url(port=6380)
    assert redis_url == "redis://localhost:6380"


def test_generator_refuses_external_service():
    req = EnvRequirement(
        name="OPENAI_API_KEY",
        classification=EnvClassification.EXTERNAL_SERVICE,
        is_required=True,
    )
    val = EnvGenerator.generate_value(req)
    assert val is None


def test_generator_auto_generates_local_secrets_and_defaults():
    jwt_req = EnvRequirement(
        name="JWT_SECRET",
        classification=EnvClassification.AUTO_GENERATABLE,
        is_required=True,
    )
    jwt_val = EnvGenerator.generate_value(jwt_req)
    assert jwt_val is not None
    assert len(jwt_val) > 20

    port_req = EnvRequirement(
        name="PORT",
        classification=EnvClassification.LOCAL_DEFAULT,
        is_required=True,
    )
    port_val = EnvGenerator.generate_value(port_req)
    assert port_val == "3000"


def test_generator_uses_postgres_config():
    req = EnvRequirement(
        name="DATABASE_URL",
        classification=EnvClassification.AUTO_GENERATABLE,
        is_required=True,
    )
    pg_cfg = PostgresConfig(
        container_name="test-pg",
        database_name="custom_db",
        host_port=5434,
        username="myuser",
        password="mypassword",
    )
    val = EnvGenerator.generate_value(req, postgres_config=pg_cfg)
    assert val == "postgresql://myuser:mypassword@localhost:5434/custom_db"
