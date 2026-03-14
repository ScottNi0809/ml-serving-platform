"""
模型文件存储层
==============

抽象存储接口 + 本地文件系统实现。
后续可扩展 S3Storage 等实现。
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

MODEL_STORE_PATH = os.environ.get("MODEL_STORE_PATH", "./model_store")


class BaseStorage(ABC):
    """存储接口抽象基类"""

    @abstractmethod
    def save(self, model_name: str, version: str, file: BinaryIO, filename: str) -> str:
        """保存模型文件，返回存储路径"""
        ...

    @abstractmethod
    def load(self, path: str) -> bytes:
        """加载模型文件内容"""
        ...

    @abstractmethod
    def delete(self, path: str) -> None:
        """删除模型文件"""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        ...


class LocalStorage(BaseStorage):
    """本地文件系统存储实现"""

    def __init__(self, base_path: str = MODEL_STORE_PATH):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, model_name: str, version: str, file: BinaryIO, filename: str) -> str:
        """保存到 model_store/{model_name}/{version}/{filename}"""
        target_dir = self.base_path / model_name / version
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        with open(target_path, "wb") as f:
            shutil.copyfileobj(file, f)

        return str(target_path)

    def load(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def delete(self, path: str) -> None:
        target = Path(path)
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

    def exists(self, path: str) -> bool:
        return Path(path).exists()


# 默认存储实例
storage = LocalStorage()
