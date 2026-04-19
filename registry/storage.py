"""
模型文件存储层
==============

抽象存储接口 + 本地文件系统实现。
后续可扩展 S3Storage 等实现。
"""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from registry.config import settings

MODEL_STORE_PATH = settings.model_store_path


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


class S3Storage(BaseStorage):
    """S3存储实现（待实现）"""

    def __init__(self, bucket_name: str, prefix: str = "models/", **kwargs):
        # 这里可以初始化boto3客户端
        self.bucket_name = bucket_name
        self.prefix = prefix
        # todo: 初始化 boto3 客户端 
        pass

    def save(self, model_name: str, version: str, file: BinaryIO, filename: str) -> str:
        raise NotImplementedError("S3Storage requires AWS_BUCKET_NAME and AWS_REGION environment variables")

    def load(self, path: str) -> bytes:
        raise NotImplementedError("S3Storage requires AWS_BUCKET_NAME and AWS_REGION environment variables")

    def delete(self, path: str) -> None:
        raise NotImplementedError("S3Storage requires AWS_BUCKET_NAME and AWS_REGION environment variables")

    def exists(self, path: str) -> bool:
        raise NotImplementedError("S3Storage requires AWS_BUCKET_NAME and AWS_REGION environment variables")


def create_storage(backend: str = "local", **kwargs) -> BaseStorage:
    """根据配置创建存储实例"""
    if backend == "local":
        return LocalStorage(**kwargs)
    elif backend == "s3":
        return S3Storage(**kwargs)
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")
