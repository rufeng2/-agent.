from pathlib import Path

from backend.db.models import Base
from backend.ecommerce.persistence.models import Base as EcommerceBase


ROOT = Path(__file__).resolve().parents[1]


def test_application_startup_does_not_run_schema_ddl():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "ensure_runtime_schema" not in source


def test_alembic_configuration_and_baseline_exist():
    assert (ROOT / "alembic.ini").exists()
    assert (ROOT / "backend" / "db" / "alembic" / "env.py").exists()
    revisions = list((ROOT / "backend" / "db" / "alembic" / "versions").glob("*.py"))
    assert revisions
    source = revisions[0].read_text(encoding="utf-8")
    assert "def upgrade()" in source
    assert "Destructive baseline downgrade is not supported" in source


def test_orm_metadata_contains_runtime_tables():
    required = {"users", "documents", "document_chunks", "audit_logs", "long_term_memories"}
    assert required <= set(Base.metadata.tables)


def test_ecommerce_runtime_tables_are_covered_by_alembic_scripts():
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "db" / "alembic" / "versions").glob("*.py")
    )
    missing = sorted(table for table in EcommerceBase.metadata.tables if f'"{table}"' not in migration_text)

    assert missing == []


def test_ecommerce_database_only_auto_creates_sqlite_schema():
    source = (ROOT / "backend" / "ecommerce" / "persistence" / "database.py").read_text(encoding="utf-8")

    assert "get_backend_name()" in source
    assert "sqlite" in source
    assert "create_all" in source
