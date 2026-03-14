"""
数据库层（SQLite）
==================

使用 SQLite 存储模型元数据和版本信息。
接口设计兼顾后续切换到 PostgreSQL 的可能。

表结构：
- models: 模型基本信息
- model_versions: 模型版本（一个模型可有多个版本）
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/registry.db")

# 从 URL 中提取文件路径
_db_path = DATABASE_URL.replace("sqlite:///", "")


def _ensure_dir():
    """确保数据库目录存在"""
    db_dir = os.path.dirname(_db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器）"""
    _ensure_dir()
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables():
    """初始化数据库表"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                framework TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'registered',
                description TEXT,
                tags TEXT DEFAULT '[]',
                default_version TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_versions (
                id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'registered',
                description TEXT,
                file_path TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE,
                UNIQUE(model_id, version)
            );
        """)
