"""Central path configuration - all data files live alongside the application."""

from pathlib import Path

# Application root: the directory containing the memorial_app package
APP_ROOT = Path(__file__).resolve().parent.parent

# All data stored inside the app directory
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "memorial.db"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_DIR = DATA_DIR / "config"
ERA_CONFIG_PATH = CONFIG_DIR / "custom_eras.json"
EXAMPLE_FILE = DATA_DIR / "example_dataset.xlsx"


def ensure_dirs():
    """Create all required directories."""
    for d in [DATA_DIR, BACKUP_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
