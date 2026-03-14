"""
自定义异常
==========

所有业务异常集中定义。
每个异常携带上下文信息，供异常处理器构造统一响应。
"""


class ModelNotFoundError(Exception):
    """模型不存在"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model '{model_name}' not found")


class ModelVersionNotFoundError(Exception):
    """模型版本不存在"""
    def __init__(self, model_name: str, version: str):
        self.model_name = model_name
        self.version = version
        super().__init__(f"Version '{version}' of model '{model_name}' not found")


class DuplicateModelError(Exception):
    """模型名称重复"""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Model '{name}' already exists")


class DuplicateVersionError(Exception):
    """模型版本重复"""
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        super().__init__(f"Version '{version}' of model '{name}' already exists")


class StorageError(Exception):
    """模型文件存储错误"""
    def __init__(self, message: str):
        super().__init__(message)
