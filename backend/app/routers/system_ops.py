import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.deps import require_admin
from app.models import User
from app.services.logs import log_operation

router = APIRouter(prefix="/system", tags=["system"])

TAILSCALE_KEYS = [
    "TS_CONTAINER_NAME",
    "TS_HOSTNAME",
    "TS_AUTHKEY",
    "TS_STATE_DIR",
    "TS_USERSPACE",
    "TS_ROUTES",
]

RUNTIME_ENV_KEYS = [
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "JWT_SECRET_KEY",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "TZ",
    "IMAGES_DIR",
    "ENABLE_WEB_OPS",
    "PROJECT_ROOT",
    "OPS_DIR",
    "REPO_URL",
    "UPDATE_BRANCH",
    "BACKEND_IMAGE",
    "FRONTEND_IMAGE",
    "APP_VERSION",
    *TAILSCALE_KEYS,
]

VALID_REF_PATTERN = re.compile(r"^[0-9A-Za-z._/-]{1,120}$")


class TailscaleConfigPayload(BaseModel):
    container_name: str = "tailscaled"
    hostname: str = "znas-server"
    auth_key: str = ""
    state_dir: str = "/var/lib/tailscale"
    userspace: bool = False
    routes: str = "192.168.1.0/24"
    apply: bool = False


class RepoConfigPayload(BaseModel):
    repo_url: str = ""
    branch: str = "main"
    initialize: bool = True


class RollbackPayload(BaseModel):
    ref: str = Field(min_length=1, max_length=120)


class TaskStartResponse(BaseModel):
    started: bool
    message: str
    pid: int | None = None
    log_path: str | None = None


def _ops_dir() -> Path:
    path = Path(settings.ops_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _repo_path() -> Path:
    normalized = str(settings.project_root or "").strip()
    if not normalized or normalized == "/workspace":
        return Path(settings.ops_dir) / "repo"
    return Path(normalized)


def _repo_config_path() -> Path:
    return _ops_dir() / "repo_config.json"


def _runtime_env_path() -> Path:
    return _ops_dir() / "runtime_env.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_runtime_env() -> dict[str, str]:
    file_data = _load_json(_runtime_env_path())
    merged: dict[str, str] = {}
    for key in RUNTIME_ENV_KEYS:
        if key in file_data and file_data[key] is not None:
            merged[key] = str(file_data[key])
        elif key in os.environ and os.environ[key] is not None:
            merged[key] = str(os.environ[key])
    return merged


def _persist_runtime_env(values: dict[str, str]) -> None:
    existing = _load_json(_runtime_env_path())
    existing.update({k: str(v) for k, v in values.items() if v is not None})
    _save_json(_runtime_env_path(), existing)


def _current_repo_config() -> dict[str, str]:
    data = _load_json(_repo_config_path())
    repo_url = str(data.get("repo_url") or settings.repo_url or "").strip()
    branch = str(data.get("branch") or settings.update_branch or "main").strip() or "main"
    return {"repo_url": repo_url, "branch": branch}


def _save_repo_config(repo_url: str, branch: str) -> None:
    _save_json(_repo_config_path(), {"repo_url": repo_url, "branch": branch})


def _run_cmd(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    process_env = os.environ.copy()
    if env:
        process_env.update({k: str(v) for k, v in env.items()})
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env=process_env,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _compose_prefix() -> list[str]:
    if _run_cmd(["docker", "compose", "version"])[0] == 0:
        return ["docker", "compose"]
    if _run_cmd(["docker-compose", "version"])[0] == 0:
        return ["docker-compose"]
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="服务器未安装 docker compose（或 docker-compose）",
    )


def _run_compose(args: list[str], cwd: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return _run_cmd([*_compose_prefix(), *args], cwd=cwd, env=env)


def _upsert_env_file(path: Path, values: dict[str, str]) -> None:
    lines: list[str] = []
    index_map: dict[str, int] = {}
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            index_map[key] = idx

    for key, value in values.items():
        line = f"{key}={value}"
        if key in index_map:
            lines[index_map[key]] = line
        else:
            lines.append(line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _ensure_repo_env_file(repo_root: Path, extra_env: dict[str, str]) -> None:
    values = _read_runtime_env()
    values.update(extra_env)
    values["PROJECT_ROOT"] = str(repo_root)
    values["OPS_DIR"] = settings.ops_dir
    _upsert_env_file(repo_root / ".env", values)


def _ensure_repo_initialized(repo_url: str, branch: str) -> Path:
    root = _repo_path()
    if (root / ".git").exists():
        return root

    if not repo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未配置仓库地址，请先在系统运维里配置 REPO_URL",
        )

    root.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run_cmd(
        ["git", "clone", "--branch", branch, "--single-branch", repo_url, str(root)],
    )
    if rc != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"克隆仓库失败: {err or out or 'unknown error'}",
        )
    return root


def _git_log_rows(repo_root: str, limit: int) -> list[dict[str, str]]:
    rc, out, err = _run_cmd(
        [
            "git",
            "-C",
            repo_root,
            "log",
            f"-n{limit}",
            "--date=iso-strict",
            "--pretty=format:%H|%h|%ad|%s",
        ]
    )
    if rc != 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err or "读取提交历史失败")

    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        rows.append(
            {
                "commit": parts[0],
                "short_commit": parts[1],
                "committed_at": parts[2],
                "subject": parts[3],
            }
        )
    return rows


@router.get("/tailscale/config")
async def get_tailscale_config(_: User = Depends(require_admin)) -> dict[str, Any]:
    env_values = _read_runtime_env()
    return {
        "container_name": env_values.get("TS_CONTAINER_NAME") or "tailscaled",
        "hostname": env_values.get("TS_HOSTNAME") or "znas-server",
        "auth_key": env_values.get("TS_AUTHKEY") or "",
        "state_dir": env_values.get("TS_STATE_DIR") or "/var/lib/tailscale",
        "userspace": (env_values.get("TS_USERSPACE") or "false").lower() == "true",
        "routes": env_values.get("TS_ROUTES") or "192.168.1.0/24",
    }


@router.put("/tailscale/config")
async def set_tailscale_config(
    payload: TailscaleConfigPayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    values = {
        "TS_CONTAINER_NAME": payload.container_name.strip() or "tailscaled",
        "TS_HOSTNAME": payload.hostname.strip() or "znas-server",
        "TS_AUTHKEY": payload.auth_key.strip(),
        "TS_STATE_DIR": payload.state_dir.strip() or "/var/lib/tailscale",
        "TS_USERSPACE": "true" if payload.userspace else "false",
        "TS_ROUTES": payload.routes.strip() or "192.168.1.0/24",
    }
    _persist_runtime_env(values)

    apply_result = "saved"
    if payload.apply:
        config = _current_repo_config()
        root = _ensure_repo_initialized(config["repo_url"], config["branch"])
        compose_env = {**_read_runtime_env(), "UPDATE_BRANCH": config["branch"], "REPO_URL": config["repo_url"]}
        _ensure_repo_env_file(root, compose_env)
        rc, out, err = _run_compose(["--profile", "tailscale", "up", "-d", "tailscale"], cwd=str(root), env=compose_env)
        if rc != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tailscale 应用失败: {err or out or 'unknown error'}",
            )
        apply_result = "applied"

    await log_operation(
        session=session,
        action="update_tailscale_config",
        target="tailscale",
        summary=f"Update tailscale config ({apply_result})",
        detail={"applied": payload.apply},
        operator_id=current_user.id,
    )
    await session.commit()

    return {"ok": True, "result": apply_result}


@router.get("/repo/config")
async def get_repo_config(_: User = Depends(require_admin)) -> dict[str, Any]:
    config = _current_repo_config()
    root = _repo_path()
    return {
        "repo_url": config["repo_url"],
        "branch": config["branch"],
        "repo_path": str(root),
        "initialized": (root / ".git").exists(),
    }


@router.put("/repo/config")
async def set_repo_config(
    payload: RepoConfigPayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    repo_url = payload.repo_url.strip()
    branch = payload.branch.strip() or "main"
    _save_repo_config(repo_url, branch)

    initialized = False
    if payload.initialize:
        root = _ensure_repo_initialized(repo_url, branch)
        _run_cmd(["git", "-C", str(root), "fetch", "origin", branch])
        initialized = True

    await log_operation(
        session=session,
        action="set_repo_config",
        target="system",
        summary="Update repository config",
        detail={"repo_url": repo_url, "branch": branch, "initialized": initialized},
        operator_id=current_user.id,
    )
    await session.commit()

    return {"ok": True, "initialized": initialized, "repo_url": repo_url, "branch": branch}


@router.get("/update/status")
async def get_update_status(_: User = Depends(require_admin)) -> dict[str, Any]:
    if not settings.enable_web_ops:
        return {"enabled": False, "message": "Web update disabled by server config"}

    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])
    branch = config["branch"]

    rc1, current_commit, err1 = _run_cmd(["git", "-C", str(root), "rev-parse", "HEAD"])
    rc2, current_branch, err2 = _run_cmd(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"])
    if rc1 != 0 or rc2 != 0:
        return {
            "enabled": True,
            "ok": False,
            "message": f"Git status failed: {err1 or err2}",
        }

    _run_cmd(["git", "-C", str(root), "fetch", "origin", branch])
    rc3, remote_commit, err3 = _run_cmd(["git", "-C", str(root), "rev-parse", f"origin/{branch}"])
    if rc3 != 0:
        return {
            "enabled": True,
            "ok": False,
            "current_branch": current_branch,
            "current_commit": current_commit,
            "message": f"Remote status failed: {err3}",
        }

    has_update = current_commit != remote_commit
    return {
        "enabled": True,
        "ok": True,
        "repo_url": config["repo_url"],
        "current_branch": current_branch,
        "current_commit": current_commit,
        "remote_commit": remote_commit,
        "has_update": has_update,
        "message": "有新版本" if has_update else "当前已是最新版本",
    }


@router.post("/update/apply", response_model=TaskStartResponse)
async def apply_update(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> TaskStartResponse:
    if not settings.enable_web_ops:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Web update disabled by server config")

    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])
    script = root / "scripts" / "nas_update.sh"
    if not script.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="更新脚本不存在")

    compose_env = {**_read_runtime_env(), "UPDATE_BRANCH": config["branch"], "REPO_URL": config["repo_url"]}
    _ensure_repo_env_file(root, compose_env)

    log_path = _ops_dir() / "update_web.log"
    log_file = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        ["bash", str(script)],
        cwd=str(root),
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env={**os.environ, **compose_env, "COMPOSE_PROJECT_NAME": "znas"},
    )
    log_file.close()

    await log_operation(
        session=session,
        action="apply_update",
        target="system",
        summary="Start web update task",
        detail={"pid": process.pid},
        operator_id=current_user.id,
    )
    await session.commit()

    return TaskStartResponse(
        started=True,
        message="更新任务已启动，稍后请刷新页面确认版本",
        pid=process.pid,
        log_path=str(log_path),
    )


@router.get("/version/state")
async def get_version_state(_: User = Depends(require_admin)) -> dict[str, Any]:
    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])

    rc1, branch, err1 = _run_cmd(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"])
    rc2, commit, err2 = _run_cmd(["git", "-C", str(root), "rev-parse", "HEAD"])
    rc3, short_commit, _ = _run_cmd(["git", "-C", str(root), "rev-parse", "--short", "HEAD"])
    rc4, tag, _ = _run_cmd(["git", "-C", str(root), "describe", "--tags", "--exact-match"])
    if rc1 != 0 or rc2 != 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err1 or err2)

    return {
        "repo_url": config["repo_url"],
        "branch": branch,
        "commit": commit,
        "short_commit": short_commit if rc3 == 0 else "",
        "tag": tag if rc4 == 0 else "",
        "checked_at": datetime.now(UTC).isoformat(),
    }


@router.get("/version/history")
async def get_version_history(limit: int = 30, _: User = Depends(require_admin)) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])
    return {"items": _git_log_rows(str(root), safe_limit)}


@router.get("/version/tags")
async def get_version_tags(limit: int = 50, _: User = Depends(require_admin)) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])
    rc, out, err = _run_cmd(["git", "-C", str(root), "tag", "--sort=-creatordate"])
    if rc != 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err or "读取标签失败")
    tags = [line.strip() for line in out.splitlines() if line.strip()][:safe_limit]
    return {"items": tags}


@router.post("/version/rollback", response_model=TaskStartResponse)
async def rollback_version(
    payload: RollbackPayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> TaskStartResponse:
    ref = payload.ref.strip()
    if not VALID_REF_PATTERN.fullmatch(ref):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="回滚版本格式不合法")

    config = _current_repo_config()
    root = _ensure_repo_initialized(config["repo_url"], config["branch"])
    script = root / "scripts" / "nas_rollback.sh"
    if not script.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回滚脚本不存在")

    compose_env = {**_read_runtime_env(), "UPDATE_BRANCH": config["branch"], "REPO_URL": config["repo_url"]}
    _ensure_repo_env_file(root, compose_env)

    log_path = _ops_dir() / "rollback_web.log"
    log_file = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        ["bash", str(script), ref],
        cwd=str(root),
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env={**os.environ, **compose_env, "COMPOSE_PROJECT_NAME": "znas"},
    )
    log_file.close()

    await log_operation(
        session=session,
        action="rollback_version",
        target=ref,
        summary=f"Start rollback to {ref}",
        detail={"pid": process.pid, "ref": ref},
        operator_id=current_user.id,
    )
    await session.commit()

    return TaskStartResponse(
        started=True,
        message=f"已开始回滚到 {ref}，请稍后刷新查看状态",
        pid=process.pid,
        log_path=str(log_path),
    )
