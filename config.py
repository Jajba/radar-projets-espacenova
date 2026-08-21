import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('RADAR_DATA_DIR', BASE_DIR / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
MASTER_XLSX = Path(os.getenv('RADAR_MASTER_XLSX', DATA_DIR / 'Radar_Projets_EspaceNova_MASTER.xlsx'))
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{DATA_DIR / 'radar.db'}")
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '25'))
MAX_DOC_BYTES = int(os.getenv('MAX_DOC_BYTES', str(30 * 1024 * 1024)))
USER_AGENT = os.getenv('RADAR_USER_AGENT', 'RadarProjetsEspaceNova/1.0 (+veille economique)')
MAX_LINKS_PER_SOURCE = int(os.getenv('MAX_LINKS_PER_SOURCE', '80'))
MIN_TEXT_CHARS = int(os.getenv('MIN_TEXT_CHARS', '250'))
