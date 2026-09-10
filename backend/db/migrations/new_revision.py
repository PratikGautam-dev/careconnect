"""Creates a new Alembic migration with a UTC-timestamp revision ID instead
of a hand-typed sequential one -- two devs on separate branches now get
different IDs by construction, so merging never collides.

Run from backend/:
    python -m db.migrations.new_revision "add foo column to bar"
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config

_ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


def main() -> None:
    if len(sys.argv) != 2:
        print('usage: python -m db.migrations.new_revision "message"', file=sys.stderr)
        raise SystemExit(1)

    alembic_cfg = Config(str(_ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("script_location", str(_ALEMBIC_INI_PATH.parent / "db" / "migrations"))
    rev_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    command.revision(alembic_cfg, message=sys.argv[1], rev_id=rev_id)


if __name__ == "__main__":
    main()
