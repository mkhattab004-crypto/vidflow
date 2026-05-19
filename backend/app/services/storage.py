import os
import logging
from pathlib import Path
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


def _dir_size_bytes(path: str) -> int:
    total = 0
    p = Path(path)
    if not p.exists():
        return 0
    for entry in p.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
    return total


def cleanup_project_storage(project_id: str) -> dict:
    ensure_project_dirs(project_id)
    project_dir = get_project_dir(project_id)
    tmp_dir = get_project_tmp_dir(project_id)
    renders_dir = get_project_renders_dir(project_id)
    keep_outputs = {"youtube_16x9.mp4", "tiktok_9x16.mp4", "instagram_1x1.mp4"}

    before_project = _dir_size_bytes(project_dir)
    before_tmp = _dir_size_bytes(tmp_dir)
    before_renders = _dir_size_bytes(renders_dir)
    deleted_files = 0

    for file_path in Path(tmp_dir).rglob("*"):
        if file_path.is_file():
            try:
                file_path.unlink()
                deleted_files += 1
            except OSError:
                continue

    for file_path in Path(renders_dir).glob("*.tmp.mp4"):
        if file_path.is_file():
            try:
                file_path.unlink()
                deleted_files += 1
            except OSError:
                continue

    for file_path in Path(renders_dir).glob("*.mp4"):
        if file_path.name in keep_outputs:
            continue
        try:
            if file_path.stat().st_size == 0:
                file_path.unlink()
                deleted_files += 1
        except OSError:
            continue

    after_project = _dir_size_bytes(project_dir)
    after_tmp = _dir_size_bytes(tmp_dir)
    after_renders = _dir_size_bytes(renders_dir)
    freed_bytes = max(before_project - after_project, 0)
    metrics = {
        "project_storage_size_mb": round(after_project / (1024 * 1024), 2),
        "tmp_storage_size_mb": round(after_tmp / (1024 * 1024), 2),
        "render_storage_size_mb": round(after_renders / (1024 * 1024), 2),
        "cleanup_deleted_file_count": deleted_files,
        "cleanup_freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "storage_full_retry_hint": "Storage full. Please delete old projects/renders or increase Railway volume size.",
    }
    logger.info(
        "project_storage_cleanup project_id=%s project_storage_size_mb=%s tmp_storage_size_mb=%s render_storage_size_mb=%s cleanup_deleted_file_count=%s cleanup_freed_mb=%s",
        project_id,
        metrics["project_storage_size_mb"],
        metrics["tmp_storage_size_mb"],
        metrics["render_storage_size_mb"],
        metrics["cleanup_deleted_file_count"],
        metrics["cleanup_freed_mb"],
    )
    return metrics
