import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from main import create_application
from core.config import get_settings

@pytest.fixture(scope="session")
def settings():
    return get_settings()

@pytest.fixture(scope="session")
def test_db_engine(settings):
    engine = create_engine(settings.TEST_DATABASE_URL, echo=True)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def db_session(test_db_engine):
    with Session(test_db_engine) as session:
        yield session

@pytest.fixture
def client(db_session):
    app = create_application()
    with TestClient(app) as test_client:
        yield test_client