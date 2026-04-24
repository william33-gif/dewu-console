from hashlib import sha1
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

from app.core.config import get_settings

PREVIEW_QUALITY = 72
MAX_PREVIEW_WIDTH = 360
MAX_PREVIEW_HEIGHT = 480


def _resolve_media_path(base_dir: Path, requested_path: str) -> Path:
    target = (base_dir / requested_path).resolve()
    try:
        target.relative_to(base_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found.") from exc

    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found.")

    return target


def _cache_path(kind: str, source: Path) -> Path:
    settings = get_settings()
    stat = source.stat()
    cache_key = "|".join(
        [
            kind,
            str(source),
            str(stat.st_mtime_ns),
            str(stat.st_size),
            str(MAX_PREVIEW_WIDTH),
            str(MAX_PREVIEW_HEIGHT),
            str(PREVIEW_QUALITY),
        ]
    )
    digest = sha1(cache_key.encode("utf-8")).hexdigest()
    return settings.resolved_project_root / "storage" / ".preview-cache" / kind / f"{digest}.webp"


def _write_preview(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as raw_image:
        image = ImageOps.exif_transpose(raw_image)
        image.thumbnail((MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT), Image.Resampling.LANCZOS)

        if image.mode in {"RGBA", "LA", "P"}:
            canvas = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            alpha = image.getchannel("A") if image.mode in {"RGBA", "LA"} else None
            canvas.paste(image.convert("RGB"), mask=alpha)
            image = canvas
        elif image.mode != "RGB":
            image = image.convert("RGB")

        image.save(destination, "WEBP", quality=PREVIEW_QUALITY, method=6)


def preview_response(base_dir: Path, requested_path: str, kind: str) -> FileResponse:
    source = _resolve_media_path(base_dir, requested_path)
    destination = _cache_path(kind, source)
    if not destination.exists():
        _write_preview(source, destination)

    return FileResponse(
        destination,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
