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
            db_type = DatabaseType.POSTGRESQL  # Default Prisma assumption if not specified
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
                    detail=f"Prisma schema with provider '{matched_provider or 'default'}'",
                    confidence=Confidence.HIGH,
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
            evidence = [
                DetectionEvidence(
                    source="alembic.ini" if ini_file.endswith("alembic.ini") else "alembic/",
                    detail="Alembic database migration configuration found",
                    confidence=Confidence.HIGH,
                    path=ini_file,
                )
            ]
            # Alembic is most commonly PostgreSQL in Python modern stacks, or generic SQL
            db_type = DatabaseType.POSTGRESQL
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
            evidence = [
                DetectionEvidence(
                    source="drizzle.config",
                    detail="Drizzle ORM configuration found",
                    confidence=Confidence.HIGH,
                    path=drizzle_files[0],
                )
            ]
            db_type = DatabaseType.POSTGRESQL
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
                    s_lower = sname.lower()

                    # PostgreSQL
                    if "postgres" in img or "timescale" in img or s_lower in ("db", "postgres", "postgresql", "database"):
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"Service '{sname}' with image '{sdef.get('image', sname)}'",
                                confidence=Confidence.HIGH,
                                path=cf,
                            )
                        ]
                        if DatabaseType.POSTGRESQL not in databases:
                            databases[DatabaseType.POSTGRESQL] = DatabaseRequirement(
                                name=DatabaseType.POSTGRESQL,
                                evidence=evidence,
                            )
                        else:
                            databases[DatabaseType.POSTGRESQL].evidence.extend(evidence)

                    # Redis
                    if "redis" in img or "valkey" in img or "dragonfly" in img or s_lower in ("redis", "cache", "queue"):
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"Service '{sname}' with image '{sdef.get('image', sname)}'",
                                confidence=Confidence.HIGH,
                                path=cf,
                            )
                        ]
                        if DatabaseType.REDIS not in databases:
                            databases[DatabaseType.REDIS] = DatabaseRequirement(
                                name=DatabaseType.REDIS,
                                evidence=evidence,
                            )
                        else:
                            databases[DatabaseType.REDIS].evidence.extend(evidence)

                        if "redis" not in services:
                            services["redis"] = ServiceRequirement(
                                name="redis",
                                service_type="cache_or_queue",
                                image=sdef.get("image"),
                                port=6379,
                                evidence=evidence,
                            )

                    # MySQL
                    if "mysql" in img or "mariadb" in img or s_lower in ("mysql", "mariadb"):
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"Service '{sname}' with image '{sdef.get('image', sname)}'",
                                confidence=Confidence.HIGH,
                                path=cf,
                            )
                        ]
                        if DatabaseType.MYSQL not in databases:
                            databases[DatabaseType.MYSQL] = DatabaseRequirement(
                                name=DatabaseType.MYSQL,
                                evidence=evidence,
                            )
                        else:
                            databases[DatabaseType.MYSQL].evidence.extend(evidence)

                    # MongoDB
                    if "mongo" in img or s_lower in ("mongo", "mongodb"):
                        evidence = [
                            DetectionEvidence(
                                source=cf,
                                detail=f"Service '{sname}' with image '{sdef.get('image', sname)}'",
                                confidence=Confidence.HIGH,
                                path=cf,
                            )
                        ]
                        if DatabaseType.MONGODB not in databases:
                            databases[DatabaseType.MONGODB] = DatabaseRequirement(
                                name=DatabaseType.MONGODB,
                                evidence=evidence,
                            )
                        else:
                            databases[DatabaseType.MONGODB].evidence.extend(evidence)

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
