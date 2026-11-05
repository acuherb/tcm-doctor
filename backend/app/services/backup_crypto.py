"""可选的备份加密（Fernet）。

设计取舍：
- 仅当 `settings.backup_passphrase` 非空时启用；默认不加密，保持现有行为，避免遗忘口令导致备份不可恢复。
- 加密文件在明文前写入魔数 `TCMENC1\\n` 作为标记；`decrypt` 遇到无魔数的旧明文备份直接原样返回，向后兼容。
- 密钥由口令经 SHA-256 确定性派生为 32 字节的 Fernet 兼容密钥（无需额外保存 salt/密钥文件）。
- 风险：口令即唯一恢复凭证。生产环境务必用强随机值并通过环境变量 TCM_BACKUP_PASSPHRASE 配置，并妥善保管。
"""
import base64
import hashlib

from app.config import settings

# 加密备份文件头魔数（明文备份不含此头，用于区分）
MAGIC = b"TCMENC1\n"


def _fernet_key() -> bytes:
    digest = hashlib.sha256((settings.backup_passphrase or "").encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encryption_enabled() -> bool:
    return bool(settings.backup_passphrase)


def encrypt(data: bytes) -> bytes:
    from cryptography.fernet import Fernet

    token = Fernet(_fernet_key()).encrypt(data)
    return MAGIC + token


def decrypt(data: bytes) -> bytes:
    from cryptography.fernet import Fernet

    if not data.startswith(MAGIC):
        # 向后兼容：旧明文备份直接返回
        return data
    if not encryption_enabled():
        raise RuntimeError("备份已加密，但当前未配置 TCM_BACKUP_PASSPHRASE，无法解密")
    token = data[len(MAGIC):]
    return Fernet(_fernet_key()).decrypt(token)


def maybe_encrypt(data: bytes) -> bytes:
    """启用加密时才加密；否则原样返回（明文）。"""
    if encryption_enabled():
        return encrypt(data)
    return data
