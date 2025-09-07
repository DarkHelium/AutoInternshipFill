import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Provide a FastAPI TestClient with an isolated SQLite DB and files dir."""
    # Ensure backend package is importable
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    # Isolated FILES_DIR for uploads/static
    files_dir = tmp_path / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FILES_DIR", str(files_dir))
    monkeypatch.setenv("CORS_ORIGINS", "*")

    # Avoid accidental usage of real API keys during tests
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    # Import app and DB after env is set
    from app import db  # type: ignore
    # Ensure models are registered on Base before create_all
    import app.models  # noqa: F401

    # Create isolated SQLite DB file under tmp_path
    test_db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Ensure the app uses this engine when main.py imports it
    db.engine = engine  # type: ignore[attr-defined]

    # Create schema on the test engine
    db.Base.metadata.create_all(bind=engine)

    # Dependency override to use the test DB session
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    from app.main import app  # type: ignore

    app.dependency_overrides[db.get_db] = override_get_db

    return TestClient(app)
