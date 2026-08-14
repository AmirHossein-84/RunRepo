"""Deterministic database and auxiliary service requirement detector."""

import re

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import (
    Confidence,
    DatabaseRequirement,
    DatabaseType,
    DetectionEvidence,
    ServiceRequirement,
)

PRISMA_PROVIDER_REGEX = re.compile(r'provider\s*=\s*"([^"]+)"')
SQLALCHEMY_URL_REGEX = re.compile(r'sqlalchemy\.url\s*=\s*([^\s]+)')
DRIZZLE_DIALECT_REGEX = re.compile(r'dialect\s*:\s*["\']([^"\']+)["\']')


class DatabaseDetector(BaseDetector):
    """Detects PostgreSQL, Redis, MySQL, SQLite, MongoDB requirements via ORMs, configs, and containers."""

    @property
    def name(self) -> str:
        return "database"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()
        databases: dict[DatabaseType, DatabaseRequirement] = {}
        services: dict[str, ServiceRequirement] = {}

        # 1. Prisma ORM detection
        prisma_files = [
            f for f in context.get_all_files() if f.endswith("schema.prisma") or f == "schema.prisma"
        ]
        for pfile in prisma_files:
            text = context.read_text(pfile)
            db_type = DatabaseType.UNKNOWN
            matched_provider = None
            if text:
                match = PRISMA_PROVIDER_REGEX.search(text)
                if match:
                    matched_provider = match.group(1).lower()
                    if "postgres" in matched_provider:
                        db_type = DatabaseType.POSTGRESQL
                    elif "mysql" in matched_provider:
                        db_type = DatabaseType.MYSQL
                    elif "sqlite" in matched_provider:
                        db_type = DatabaseType.SQLITE
                    elif "mongo" in matched_provider:
                        db_type = DatabaseType.MONGODB

            evidence = [
                DetectionEvidence(
                    source="schema.prisma",
                    detail=f"Prisma schema with provider '{matched_provider or 'unspecified'}'",
                    confidence=Confidence.HIGH if matched_provider else Confidence.MEDIUM,
                    path=pfile,
                )
            ]
            if db_type not in databases:
                databases[db_type] = DatabaseRequirement(
                    name=db_type,
                    orm="prisma",
                    connection_var="DATABASE_URL",
                    evidence=evidence,
                )
            else:
                databases[db_type].evidence.extend(evidence)
                if not databases[db_type].orm:
                    databases[db_type].orm = "prisma"

        # 2. Alembic detection
        alembic_files = [
            f
            for f in context.get_all_files()
            if f.endswith("alembic.ini") or f == "alembic.ini" or "/alembic/" in f or f.startswith("alembic/")
        ]
        if alembic_files:
            ini_file = next((f for f in alembic_files if f.endswith("alembic.ini")), alembic_files[0])
            ini_text = context.read_text(ini_file) if ini_file.endswith("alembic.ini") else None
            
            db_type = DatabaseType.UNKNOWN
            detail_msg = "Alembic database migration configuration found"
            
            if ini_text:
                url_match = SQLALCHEMY_URL_REGEX.search(ini_text)
                if url_match:
                    raw_url = url_match.group(1).lower()
                    if "postgres" in raw_url:
                        db_type = DatabaseType.POSTGRESQL
                        detail_msg = f"Alembic configured with PostgreSQL url: {url_match.group(1)}"
                    elif "mysql" in raw_url:
                        db_type = DatabaseType.MYSQL
                        detail_msg = f"Alembic configured with MySQL url: {url_match.group(1)}"
                    elif "sqlite" in raw_url:
                        db_type = DatabaseType.SQLITE
                        detail_msg = f"Alembic configured with SQLite url: {url_match.group(1)}"

            # If no URL in alembic.ini, check for database driver dependencies
            if db_type == DatabaseType.UNKNOWN:
                all_text = " ".join(
                    filter(None, [context.read_text("requirements.txt"), context.read_text("pyproject.toml")])
                ).lower()
                if any(p in all_text for p in ("psycopg", "asyncpg", "pg8000")):
                    db_type = DatabaseType.POSTGRESQL
                    detail_msg += " (PostgreSQL driver dependency detected)"
                elif any(m in all_text for m in ("mysqlclient", "pymysql", "asyncmy")):
                    db_type = DatabaseType.MYSQL
                    detail_msg += " (MySQL driver dependency detected)"
                elif "aiosqlite" in all_text:
                    db_type = DatabaseType.SQLITE
                    detail_msg += " (SQLite driver dependency detected)"

            evidence = [
                DetectionEvidence(
                    source="alembic.ini" if ini_file.endswith("alembic.ini") else "alembic/",
                    detail=detail_msg,
                    confidence=Confidence.HIGH if db_type != DatabaseType.UNKNOWN else Confidence.MEDIUM,
                    path=ini_file,
                )
            ]
            if db_type not in databases:
                databases[db_type] = DatabaseRequirement(
                    name=db_type,
                    orm="alembic",
                    connection_var="DATABASE_URL",
                    evidence=evidence,
                )
            else:
                databases[db_type].evidence.extend(evidence)
                if not databases[db_type].orm:
                    databases[db_type].orm = "alembic"

        # 3. Drizzle ORM detection
        drizzle_files = [
            f for f in context.get_all_files() if "drizzle.config" in f or f.startswith("drizzle/")
        ]
        if drizzle_files:
            cfg_file = next((f for f in drizzle_files if "drizzle.config" in f), drizzle_files[0])
            cfg_text = context.read_text(cfg_file) if "drizzle.config" in cfg_file else None
            
            db_type = DatabaseType.UNKNOWN
            detail_msg = "Drizzle ORM configuration found"
            
            if cfg_text:
                dialect_match = DRIZZLE_DIALECT_REGEX.search(cfg_text)
                if dialect_match:
                    dialect = dialect_match.group(1).lower()
                    if dialect in ("postgresql", "pg"):
                        db_type = DatabaseType.POSTGRESQL
                        detail_msg = f"Drizzle configured with dialect '{dialect}'"
                    elif dialect == "mysql":
                        db_type = DatabaseType.MYSQL
                        detail_msg = "Drizzle configured with dialect 'mysql'"
                    elif dialect == "sqlite":
                        db_type = DatabaseType.SQLITE
                        detail_msg = "Drizzle configured with dialect 'sqlite'"

            if db_type == DatabaseType.UNKNOWN:
                pkg_text = (context.read_text("package.json") or "").lower()
                if any(p in pkg_text for p in ("@vercel/postgres", "@neondatabase/serverless", "pg", "postgres")):
                    db_type = DatabaseType.POSTGRESQL
                    detail_msg += " (PostgreSQL driver dependency detected)"
                elif "mysql2" in pkg_text:
                    db_type = DatabaseType.MYSQL
                    detail_msg += " (MySQL driver dependency detected)"
                elif any(s in pkg_text for s in ("better-sqlite3", "@libsql/client")):
                    db_type = DatabaseType.SQLITE
                    detail_msg += " (SQLite driver dependency detected)"

            evidence = [
                DetectionEvidence(
                    source="drizzle.config",
                    detail=detail_msg,
                    confidence=Confidence.HIGH if db_type != DatabaseType.UNKNOWN else Confidence.MEDIUM,
                    path=cfg_file,
                )
            ]
            if db_type not in databases:
                databases[db_type] = DatabaseRequirement(
                    name=db_type,
                    orm="drizzle",
                    connection_var="DATABASE_URL",
                    evidence=evidence,
                )
            else:
                databases[db_type].evidence.extend(evidence)

        # 4. Check Docker Compose files for database & redis services
        compose_files = (
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
        )
        for cf in compose_files:
            if not context.has_file(cf):
                continue

            cdata = context.read_yaml(cf)
            if not isinstance(cdata, dict):
                continue

            raw_services = cdata.get("services")
            if isinstance(raw_services, dict):
                for sname, sdef in raw_services.items():
                    if not isinstance(sdef, dict):
                        continue

                    img = str(sdef.get("image", "")).lower()
                    s_lower = str(sname).lower()
                    raw_env = sdef.get("environment", {})
                    env_keys = (
                        [k.upper() for k in raw_env.keys()]
                        if isinstance(raw_env, dict)
                        else [str(e).split("=")[0].upper() for e in raw_env if isinstance(e, str)]
                    )

                    # Match by Image first (highest accuracy)
                    matched_db: DatabaseType | None = None
                    if "postgres" in img or "timescale" in img:
                        matched_db = DatabaseType.POSTGRESQL
                    elif "mysql" in img or "mariadb" in img:
                        matched_db = DatabaseType.MYSQL
                    elif "mongo" in img:
                        matched_db = DatabaseType.MONGODB
                    elif "redis" in img or "valkey" in img or "dragonfly" in img or "keydb" in img:
                        matched_db = DatabaseType.REDIS
                    # Fallback to Service Name & Environment Keys
                    elif "postgres" in s_lower:
                        matched_db = DatabaseType.POSTGRESQL
                    elif "mysql" in s_lower or "mariadb" in s_lower:
                        matched_db = DatabaseType.MYSQL
                    elif "mongo" in s_lower:
                        matched_db = DatabaseType.MONGODB
                    elif "redis" in s_lower or s_lower in ("cache", "queue"):
                        matched_db = DatabaseType.REDIS
                    elif s_lower in ("db", "database"):
                        if any("POSTGRES" in k for k in env_keys):
                            matched_db = DatabaseType.POSTGRESQL
                        elif any("MYSQL" in k or "MARIADB" in k for k in env_keys):
                            matched_db = DatabaseType.MYSQL
                        elif any("MONGO" in k for k in env_keys):
                            matched_db = DatabaseType.MONGODB
                        else:
                            matched_db = DatabaseType.UNKNOWN

                    if matched_db is not None:
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"Service '{sname}' with image '{sdef.get('image', sname)}'",
                                confidence=Confidence.HIGH if img else Confidence.MEDIUM,
                                path=cf,
                            )
                        ]
                        if matched_db not in databases:
                            databases[matched_db] = DatabaseRequirement(
                                name=matched_db,
                                evidence=evidence,
                            )
                        else:
                            databases[matched_db].evidence.extend(evidence)

                    # Redis as an auxiliary ServiceRequirement
                    if matched_db == DatabaseType.REDIS or "redis" in s_lower:
                        if "redis" not in services:
                            services["redis"] = ServiceRequirement(
                                name="redis",
                                service_type="cache_or_queue",
                                image=sdef.get("image"),
                                port=6379,
                                evidence=[
                                    DetectionEvidence(
                                        source=cf,
                                        detail=f"Redis service '{sname}' in compose",
                                        confidence=Confidence.HIGH,
                                        path=cf,
                                    )
                                ],
                            )

                    # RabbitMQ
                    if "rabbitmq" in img or s_lower == "rabbitmq":
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"RabbitMQ message broker service '{sname}'",
                                confidence=Confidence.HIGH,
                                path=cf,
                            )
                        ]
                        services["rabbitmq"] = ServiceRequirement(
                            name="rabbitmq",
                            service_type="message_broker",
                            image=sdef.get("image"),
                            port=5672,
                            evidence=evidence,
                        )

        result.databases.extend(databases.values())
        result.services.extend(services.values())
        return result
