import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.deps import get_current_user
from app.models import User
from app.schemas import UploadResponse

router = APIRouter(tags=["upload"])
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    # 兼容未安装 heif 扩展的场景，常规格式仍可正常上传
    pass


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> UploadResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持图片上传")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTS:
        suffix = ".jpg"

    file_id = uuid.uuid4().hex
    original_rel = Path("originals") / f"{file_id}{suffix}"
    thumb_rel = Path("thumbs") / f"{file_id}.jpg"

    original_abs = Path(settings.images_dir) / original_rel
    thumb_abs = Path(settings.images_dir) / thumb_rel
    original_abs.parent.mkdir(parents=True, exist_ok=True)
    thumb_abs.parent.mkdir(parents=True, exist_ok=True)
    original_abs.write_bytes(file_bytes)

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail((300, 300))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(thumb_abs, format="JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError):
        original_abs.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法识别或处理该图片") from None

    original_path = original_rel.as_posix()
    thumb_path = thumb_rel.as_posix()
    return UploadResponse(
        original_path=original_path,
        thumb_path=thumb_path,
        original_url=str(request.url_for("media", path=original_path)),
        thumb_url=str(request.url_for("media", path=thumb_path)),
    )
