import pytest
from pathlib import Path

from registry.storage import S3Storage, LocalStorage, create_storage

class TestStorage:

    def test_create_local_storage(self):
        store = create_storage(backend="local", base_path="./test_model_store")
        assert isinstance(store, LocalStorage)
        assert store.base_path == Path("./test_model_store")

    def test_create_storage_returns_s3_storage(self):
        store = create_storage(backend="s3", bucket_name="test-bucket", prefix="test-prefix/")
        assert isinstance(store, S3Storage)
        assert store.bucket_name == "test-bucket"
        assert store.prefix == "test-prefix/"

    def test_s3_storage_methods_raise_not_implemented(self):
        store = create_storage(backend="s3", bucket_name="test-bucket", prefix="test-prefix/")

        with pytest.raises(NotImplementedError, match="S3Storage requires AWS_BUCKET_NAME and AWS_REGION environment variables"):
            store.save("test", "1.0.0", None, "model.pt")

    def test_create_storage_raises_for_unsupported_backend(self):
        with pytest.raises(ValueError, match="Unsupported storage backend: gcs"):
            create_storage(backend="gcs")