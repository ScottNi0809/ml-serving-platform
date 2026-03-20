"""
模型 CRUD 路由 + 版本管理
=========================

/api/v1/models — 模型注册、查询、更新、删除
/api/v1/models/{name}/versions — 版本管理
/api/v1/models/{name}/versions/{version}/upload — 文件上传
"""

import json
import uuid
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from fastapi.responses import FileResponse

from registry.database import get_db
from registry.dependencies import get_current_user
from registry.storage import BaseStorage
from registry.exceptions import (
    DuplicateModelError,
    DuplicateVersionError,
    ModelNotFoundError,
    ModelVersionNotFoundError,
)
from registry.schemas import (
    ModelCreate,
    ModelFramework,
    ModelListResponse,
    ModelResponse,
    ModelStatus,
    ModelUpdate,
    ModelVersionCreate,
    ModelVersionResponse,
)
from registry.dependencies import get_storage

router = APIRouter(
    prefix="/api/v1/models",
    tags=["Models"],
)


# ============================================================
# Helper: row → response dict
# ============================================================

def _model_row_to_response(row) -> dict:
    """将数据库行转为 ModelResponse 兼容的 dict"""
    return {
        "id": row["id"],
        "name": row["name"],
        "framework": row["framework"],
        "status": row["status"],
        "description": row["description"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "created_at": row["created_at"],
        "default_version": row["default_version"],
        "version_count": row["version_count"] if "version_count" in row.keys() else 0,
    }


def _version_row_to_response(row) -> dict:
    return {
        "id": row["id"],
        "model_name": row["model_name"],
        "version": row["version"],
        "status": row["status"],
        "description": row["description"],
        "file_path": row["file_path"],
        "created_at": row["created_at"],
        "is_default": bool(row["is_default"]),
    }


def _parse_version(version: str) -> tuple[int, int, int]:
    """解析语义化版本号"""
    try:
        major, minor, patch = version.split(".")
        return int(major), int(minor), int(patch)
    except Exception:
        raise ValueError(f"Invalid version format: {version}")


def _next_version(conn, model_id: str) -> str:
    """查询当前最高版本号，Patch + 1。无版本时返回 1.0.0"""
    rows = conn.execute(
        "SELECT version FROM model_versions WHERE model_id = ?",
        (model_id,),
    ).fetchall()

    if not rows:
        return "1.0.0"

    try:
        versions = [row["version"] for row in rows]
        highest = max(versions, key=lambda v: _parse_version(v))
        major, minor, patch = _parse_version(highest)
        patch += 1
        return f"{major}.{minor}.{patch}"
    except ValueError:
        return "1.0.0"


# ============================================================
# 模型 CRUD
# ============================================================

@router.post("", status_code=201, response_model=ModelResponse)
async def create_model(
    body: ModelCreate,
    user: dict = Depends(get_current_user),
):
    """注册新模型"""
    model_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(body.tags)

    with get_db() as conn:
        # 检查重名
        existing = conn.execute(
            "SELECT id FROM models WHERE name = ?", (body.name,)
        ).fetchone()
        if existing:
            raise DuplicateModelError(body.name)

        conn.execute(
            """INSERT INTO models (id, name, framework, status, description, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (model_id, body.name, body.framework.value, "registered", body.description, tags_json, now),
        )

    return {
        "id": model_id,
        "name": body.name,
        "framework": body.framework,
        "status": "registered",
        "description": body.description,
        "tags": body.tags,
        "created_at": now,
        "default_version": None,
        "version_count": 0,
    }


@router.get("", response_model=ModelListResponse)
async def list_models(
    framework: Optional[ModelFramework] = Query(None, description="按框架筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """获取模型列表"""
    with get_db() as conn:
        # 构建查询
        where_clauses = []
        params: list = []
        if framework:
            where_clauses.append("m.framework = ?")
            params.append(framework.value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 总数
        total = conn.execute(
            f"SELECT COUNT(*) as cnt FROM models m {where_sql}", params
        ).fetchone()["cnt"]

        # 分页查询（带版本计数）
        rows = conn.execute(
            f"""SELECT m.*, COUNT(v.id) as version_count
                FROM models m
                LEFT JOIN model_versions v ON m.id = v.model_id
                {where_sql}
                GROUP BY m.id
                ORDER BY m.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, skip],
        ).fetchall()

    items = [_model_row_to_response(r) for r in rows]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{model_name}", response_model=ModelResponse)
async def get_model(
    model_name: str = Path(..., description="模型名称"),
    user: dict = Depends(get_current_user),
):
    """获取模型详情"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT m.*, COUNT(v.id) as version_count
               FROM models m
               LEFT JOIN model_versions v ON m.id = v.model_id
               WHERE m.name = ?
               GROUP BY m.id""",
            (model_name,),
        ).fetchone()

    if not row:
        raise ModelNotFoundError(model_name)
    return _model_row_to_response(row)


@router.patch("/{model_name}", response_model=ModelResponse)
async def update_model(
    updates: ModelUpdate,
    model_name: str = Path(..., description="模型名称"),
    user: dict = Depends(get_current_user),
):
    """更新模型元数据"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM models WHERE name = ?", (model_name,)).fetchone()
        if not row:
            raise ModelNotFoundError(model_name)

        set_clauses = []
        params: list = []
        if updates.description is not None:
            set_clauses.append("description = ?")
            params.append(updates.description)
        if updates.tags is not None:
            set_clauses.append("tags = ?")
            params.append(json.dumps(updates.tags))

        if set_clauses:
            params.append(model_name)
            conn.execute(
                f"UPDATE models SET {', '.join(set_clauses)} WHERE name = ?",
                params,
            )

    # 返回更新后的模型
    return await get_model(model_name, user)


@router.get("/{model_name}/versions/{version}/download")
async def download_model_file(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user)
):
    # 下载模型文件
    with get_db() as conn:
        row = conn.execute("SELECT file_path FROM model_versions WHERE model_name = ? AND version = ?", (model_name, version)).fetchone()
        # 没找到记录”或者“找到但文件路径为空”
        if not row or not row["file_path"]:
            raise ModelVersionNotFoundError(model_name, version)

        file_path = row["file_path"]

        # 磁盘文件被意外删除
        if not os.path.exists(file_path):
            raise ModelVersionNotFoundError(model_name, version)

    return FileResponse(file_path, media_type="application/octet-stream", filename=os.path.basename(file_path))


@router.delete("/{model_name}", status_code=204)
async def delete_model(
    model_name: str = Path(..., description="模型名称"),
    user: dict = Depends(get_current_user),
    store: BaseStorage = Depends(get_storage),
):
    """删除模型（级联删除所有版本和文件）"""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM models WHERE name = ?", (model_name,)).fetchone()
        if not row:
            raise ModelNotFoundError(model_name)

        # 删除存储的文件
        versions = conn.execute(
            "SELECT file_path FROM model_versions WHERE model_id = ?", (row["id"],)
        ).fetchall()
        for v in versions:
            if v["file_path"]:
                store.delete(v["file_path"])

        conn.execute("DELETE FROM models WHERE id = ?", (row["id"],))


# ============================================================
# 版本管理
# ============================================================

@router.post("/{model_name}/versions", status_code=201, response_model=ModelVersionResponse)
async def create_version(
    body: ModelVersionCreate,
    model_name: str = Path(..., description="模型名称"),
    user: dict = Depends(get_current_user),
):
    """为模型创建新版本"""
    version_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        model = conn.execute("SELECT id FROM models WHERE name = ?", (model_name,)).fetchone()
        if not model:
            raise ModelNotFoundError(model_name)
        
        # --- 新增：自动版本号 ---
        if body.version is None:
            body.version = _next_version(conn, model["id"])

        # 检查版本号是否已存在
        existing = conn.execute(
            "SELECT id FROM model_versions WHERE model_id = ? AND version = ?",
            (model["id"], body.version),
        ).fetchone()
        if existing:
            raise DuplicateVersionError(model_name, body.version)

        # 如果是第一个版本，自动设为默认
        version_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM model_versions WHERE model_id = ?",
            (model["id"],),
        ).fetchone()["cnt"]
        is_default = 1 if version_count == 0 else 0

        conn.execute(
            """INSERT INTO model_versions
               (id, model_id, model_name, version, status, description, is_default, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, model["id"], model_name, body.version, "registered", body.description, is_default, now),
        )

        if is_default:
            conn.execute(
                "UPDATE models SET default_version = ? WHERE id = ?",
                (body.version, model["id"]),
            )

    return {
        "id": version_id,
        "model_name": model_name,
        "version": body.version,
        "status": "registered",
        "description": body.description,
        "file_path": None,
        "created_at": now,
        "is_default": bool(is_default),
    }


@router.get("/{model_name}/versions", response_model=list[ModelVersionResponse])
async def list_versions(
    model_name: str = Path(..., description="模型名称"),
    user: dict = Depends(get_current_user),
):
    """列出模型的所有版本"""
    with get_db() as conn:
        model = conn.execute("SELECT id FROM models WHERE name = ?", (model_name,)).fetchone()
        if not model:
            raise ModelNotFoundError(model_name)

        rows = conn.execute(
            "SELECT * FROM model_versions WHERE model_id = ? ORDER BY created_at DESC",
            (model["id"],),
        ).fetchall()

    return [_version_row_to_response(r) for r in rows]


@router.get("/{model_name}/versions/{version}", response_model=ModelVersionResponse)
async def get_version(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user),
):
    """获取指定版本详情"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.* FROM model_versions v
               JOIN models m ON v.model_id = m.id
               WHERE m.name = ? AND v.version = ?""",
            (model_name, version),
        ).fetchone()

    if not row:
        raise ModelVersionNotFoundError(model_name, version)
    return _version_row_to_response(row)


@router.post("/{model_name}/versions/{version}/upload", response_model=ModelVersionResponse)
async def upload_model_file(
    model_name: str = Path(...),
    version: str = Path(...),
    file: UploadFile = File(..., description="模型权重文件"),
    user: dict = Depends(get_current_user),
    store: BaseStorage = Depends(get_storage),
):
    """为指定版本上传模型文件"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.* FROM model_versions v
               JOIN models m ON v.model_id = m.id
               WHERE m.name = ? AND v.version = ?""",
            (model_name, version),
        ).fetchone()

        if not row:
            raise ModelVersionNotFoundError(model_name, version)

        # 保存文件
        file_path = store.save(model_name, version, file.file, file.filename)

        # 更新数据库
        conn.execute(
            "UPDATE model_versions SET file_path = ?, status = 'ready' WHERE id = ?",
            (file_path, row["id"]),
        )
        conn.execute(
            "UPDATE models SET status = 'ready' WHERE name = ?",
            (model_name,),
        )

    return {
        "id": row["id"],
        "model_name": model_name,
        "version": version,
        "status": "ready",
        "description": row["description"],
        "file_path": file_path,
        "created_at": row["created_at"],
        "is_default": bool(row["is_default"]),
    }


@router.put("/{model_name}/versions/{version}/default", response_model=ModelVersionResponse)
async def set_default_version(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user),
):
    """设置默认版本"""
    with get_db() as conn:
        model = conn.execute("SELECT id FROM models WHERE name = ?", (model_name,)).fetchone()
        if not model:
            raise ModelNotFoundError(model_name)

        target = conn.execute(
            "SELECT * FROM model_versions WHERE model_id = ? AND version = ?",
            (model["id"], version),
        ).fetchone()
        if not target:
            raise ModelVersionNotFoundError(model_name, version)

        # 取消旧默认
        conn.execute(
            "UPDATE model_versions SET is_default = 0 WHERE model_id = ?",
            (model["id"],),
        )
        # 设置新默认
        conn.execute(
            "UPDATE model_versions SET is_default = 1 WHERE id = ?",
            (target["id"],),
        )
        conn.execute(
            "UPDATE models SET default_version = ? WHERE id = ?",
            (version, model["id"]),
        )

    return {
        "id": target["id"],
        "model_name": model_name,
        "version": version,
        "status": target["status"],
        "description": target["description"],
        "file_path": target["file_path"],
        "created_at": target["created_at"],
        "is_default": True,
    }


@router.delete("/{model_name}/versions/{version}/file", status_code=204)
async def delete_version_file(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user),
    store: BaseStorage = Depends(get_storage),
):
    """删除版本的模型文件，保留版本记录"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.id, v.file_path FROM model_versions v
               JOIN models m ON v.model_id = m.id
               WHERE m.name = ? AND v.version = ?""",
            (model_name, version),
        ).fetchone()
        if not row:
            raise ModelVersionNotFoundError(model_name, version)

        if row["file_path"]:
            store.delete(row["file_path"])
            conn.execute(
                "UPDATE model_versions SET file_path = NULL, status = 'registered' WHERE id = ?",
                (row["id"],),
            )


@router.post("/{model_name}/versions/{version}/cleanup")
async def cleanup_version_file(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user),
    store: BaseStorage = Depends(get_storage),
):
    """清理指定版本的模型文件"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.id, v.file_path
            FROM model_versions v
            JOIN models m ON v.model_id = m.id
            WHERE m.name = ? AND v.version = ?""",
            (model_name, version),
        ).fetchone()
        if not row:
            raise ModelVersionNotFoundError(model_name, version)

        if row["file_path"]:
            store.delete(row["file_path"])
            conn.execute(
                "UPDATE model_versions SET file_path = NULL, status = 'registered' WHERE id = ?",
                (row["id"],),
            )

    return {"message": "cleanup completed"}


@router.delete("/{model_name}/versions/{version}", status_code=204)
async def delete_version(
    model_name: str = Path(...),
    version: str = Path(...),
    user: dict = Depends(get_current_user),
    store: BaseStorage = Depends(get_storage),
):
    """删除指定版本"""
    with get_db() as conn:
        target = conn.execute(
            """SELECT v.*, m.id AS model_id
               FROM model_versions v
               JOIN models m ON v.model_id = m.id
               WHERE m.name = ? AND v.version = ?""",
            (model_name, version),
        ).fetchone()
        if not target:
            model = conn.execute("SELECT id FROM models WHERE name = ?", (model_name,)).fetchone()
            if not model:
                raise ModelNotFoundError(model_name)
            raise ModelVersionNotFoundError(model_name, version)

        # 删除存储的文件
        if target["file_path"]:
            store.delete(target["file_path"])

        conn.execute("DELETE FROM model_versions WHERE id = ?", (target["id"],))

        # 如果删除的是默认版本，重新选择并同步新的默认版本
        if target["is_default"]:
            rows = conn.execute(
                "SELECT version FROM model_versions WHERE model_id = ? ORDER BY created_at DESC",
                (target["model_id"],),
            ).fetchall()

            if not rows:
                conn.execute(
                    "UPDATE models SET default_version = NULL WHERE id = ?",
                    (target["model_id"],),
                )
            else:
                versions = [row["version"] for row in rows]
                try:
                    new_default = max(versions, key=_parse_version)
                except ValueError:
                    # 版本号异常时，回退到最新创建版本
                    new_default = versions[0]

                conn.execute(
                    "UPDATE model_versions SET is_default = 0 WHERE model_id = ?",
                    (target["model_id"],),
                )
                conn.execute(
                    "UPDATE model_versions SET is_default = 1 WHERE model_id = ? AND version = ?",
                    (target["model_id"], new_default),
                )
                conn.execute(
                    "UPDATE models SET default_version = ? WHERE id = ?",
                    (new_default, target["model_id"]),
                )
    
