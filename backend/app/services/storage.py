import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def get_storage_root() -> str:
    root = settings.VIDFLOW_STORAGE_DIR or "/tmp/vidflow_storage"
    os.makedirs(root, exist_ok=True)
    logger.info("storage_root=%s", root)
    return root


def get_project_dir(project_id: str) -> str:
    project_dir = os.path.join(get_storage_root(), "projects", str(project_id))
    os.makedirs(project_dir, exist_ok=True)
    logger.info("project_storage_dir=%s", project_dir)
    return project_dir


def get_project_assets_dir(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "assets")


def get_project_audio_dir(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "audio")


def get_project_renders_dir(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "renders")


def get_project_subtitles_dir(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "subtitles")


def get_project_tmp_dir(project_id: str) -> str:
    return os.path.join(get_project_dir(project_id), "tmp")


def ensure_project_dirs(project_id: str) -> None:
    for p in [
        get_project_assets_dir(project_id),
        get_project_audio_dir(project_id),
        get_project_renders_dir(project_id),
        get_project_subtitles_dir(project_id),
        get_project_tmp_dir(project_id),
    ]:
        os.makedirs(p, exist_ok=True)
