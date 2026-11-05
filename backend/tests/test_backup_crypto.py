"""备份加密：Fernet 加解密、明文兼容、自动备份集成、导入解密。"""
import pytest

from app.config import settings
from app.services import backup_crypto
from app import auto_backup


@pytest.fixture
def with_passphrase():
    old = settings.backup_passphrase
    settings.backup_passphrase = "strong-test-passphrase-123"
    try:
        yield
    finally:
        settings.backup_passphrase = old


def test_encrypt_decrypt_roundtrip(with_passphrase):
    data = b"SQLite format 3\x00 hello world patient privacy"
    enc = backup_crypto.encrypt(data)
    assert enc != data
    assert enc.startswith(backup_crypto.MAGIC)
    assert backup_crypto.decrypt(enc) == data


def test_decrypt_plaintext_passthrough(with_passphrase):
    # 旧明文备份（无魔数头）应原样返回，向后兼容
    raw = b"SQLite format 3\x00 some plaintext db"
    assert backup_crypto.decrypt(raw) == raw


def test_maybe_encrypt_no_passphrase_is_noop():
    old = settings.backup_passphrase
    settings.backup_passphrase = ""
    try:
        data = b"some data"
        assert backup_crypto.maybe_encrypt(data) == data
        assert backup_crypto.encryption_enabled() is False
    finally:
        settings.backup_passphrase = old


def test_decrypt_without_passphrase_raises():
    old = settings.backup_passphrase
    settings.backup_passphrase = ""  # 加密文件但当前未配置口令
    try:
        enc = backup_crypto.MAGIC + b"token"
        with pytest.raises(RuntimeError):
            backup_crypto.decrypt(enc)
    finally:
        settings.backup_passphrase = old


def test_create_backup_is_encrypted_and_recoverable(client, with_passphrase, tmp_path, monkeypatch):
    monkeypatch.setattr(auto_backup, "backup_dir", lambda: tmp_path)
    # 触发一次自动备份快照（加密）
    info = auto_backup.create_backup("manual")
    f = tmp_path / info["name"]
    assert f.is_file()
    enc = f.read_bytes()
    assert enc.startswith(backup_crypto.MAGIC)
    # 解密后应恢复为合法 SQLite 文件
    raw = backup_crypto.decrypt(enc)
    assert raw[:16].startswith(b"SQLite format 3\x00")


def test_create_backup_plaintext_without_passphrase(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_passphrase", "")
    monkeypatch.setattr(auto_backup, "backup_dir", lambda: tmp_path)
    info = auto_backup.create_backup("manual")
    f = tmp_path / info["name"]
    enc = f.read_bytes()
    # 无口令：明文，不含魔数头
    assert not enc.startswith(backup_crypto.MAGIC)
    assert enc[:16].startswith(b"SQLite format 3\x00")
