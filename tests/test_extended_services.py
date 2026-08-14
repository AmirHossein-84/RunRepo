"""Unit tests for MySQL, MongoDB, RabbitMQ, and MinIO service managers."""

from runrepo.executor.process import MockProcessExecutor
from runrepo.services.minio import MinioManager
from runrepo.services.models import MinioConfig, MongoDBConfig, MySQLConfig, RabbitMQConfig, ResourceType, ServiceType
from runrepo.services.mongodb import MongoDBManager
from runrepo.services.mysql import MySQLManager
from runrepo.services.rabbitmq import RabbitMQManager


def test_mysql_provision():
    cfg = MySQLConfig(
        container_name="test-mysql",
        host_port=3306,
        database_name="appdb",
    )
    mock = MockProcessExecutor()

    ok, msg, res = MySQLManager.provision(cfg, project_path="/test", executor=mock)
    assert ok is True
    assert res is not None
    assert res.service_type == ServiceType.MYSQL
    assert res.ports == [3306]


def test_mongodb_provision():
    cfg = MongoDBConfig(
        container_name="test-mongo",
        host_port=27017,
        database_name="myapp",
    )
    mock = MockProcessExecutor()

    ok, msg, res = MongoDBManager.provision(cfg, project_path="/test", executor=mock)
    assert ok is True
    assert res is not None
    assert res.service_type == ServiceType.MONGODB


def test_rabbitmq_provision():
    cfg = RabbitMQConfig(
        container_name="test-rabbitmq",
        host_port=5672,
        mgmt_port=15672,
    )
    mock = MockProcessExecutor()

    ok, msg, res = RabbitMQManager.provision(cfg, project_path="/test", executor=mock)
    assert ok is True
    assert res is not None
    assert res.service_type == ServiceType.RABBITMQ
    assert 5672 in res.ports
    assert 15672 in res.ports


def test_minio_provision():
    cfg = MinioConfig(
        container_name="test-minio",
        host_port=9000,
        console_port=9001,
    )
    mock = MockProcessExecutor()

    ok, msg, res = MinioManager.provision(cfg, project_path="/test", executor=mock)
    assert ok is True
    assert res is not None
    assert res.service_type == ServiceType.MINIO
    assert 9000 in res.ports
    assert 9001 in res.ports
