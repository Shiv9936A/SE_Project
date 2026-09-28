"""Initialize or upgrade the configured database to the Alembic head revision."""
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    command.upgrade(config, "head")
    print("Database initialized to the latest Alembic revision.")


if __name__ == "__main__":
    main()
