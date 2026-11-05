"""自动备份：在线快照合法性、配置持久化、保留份数与端点权限/下载白名单。"""
import sqlite3

from app import auto_backup


def test_create_backup_produces_valid_sqlite(client):
    info = auto_backup.create_backup("manual")
    path = auto_backup.backup_dir() / info["name"]
    assert path.is_file()
    assert path.read_bytes()[:16].startswith(b"SQLite format 3\x00")
    with sqlite3.connect(str(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] >= 1
    assert info["reason"] == "manual"
    assert any(i["name"] == info["name"] for i in auto_backup.list_backups())


def test_config_roundtrip_and_prune(client):
    original = auto_backup.load_config()
    try:
        cfg = auto_backup.save_config({"enabled": False, "interval_hours": 6, "keep": 2})
        assert cfg == {"enabled": False, "interval_hours": 6, "keep": 2}
        assert auto_backup.load_config() == cfg
        # 关闭定时后 run_cycle 不再产生快照，但 force 的手动备份仍可用
        assert auto_backup.run_cycle() is None
        for _ in range(4):
            auto_backup.create_backup("manual")
        auto_backup.run_cycle(force=True)
        assert len(auto_backup.list_backups()) <= 2
    finally:
        auto_backup.save_config(original)


def test_auto_backup_endpoints(client, auth_headers):
    original = auto_backup.load_config()
    try:
        status = client.get("/api/v1/backup/auto/status", headers=auth_headers)
        assert status.status_code == 200, status.text
        data = status.json()
        assert "config" in data and "dir" in data and "items" in data

        updated = client.put(
            "/api/v1/backup/auto/config",
            json={"enabled": False, "interval_hours": 6, "keep": 3},
            headers=auth_headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["keep"] == 3
        assert client.put(
            "/api/v1/backup/auto/config", json={"interval_hours": 0}, headers=auth_headers,
        ).status_code == 422

        run = client.post("/api/v1/backup/auto/run", headers=auth_headers)
        assert run.status_code == 200, run.text
        name = run.json()["name"]

        dl = client.get(f"/api/v1/backup/auto/download/{name}", headers=auth_headers)
        assert dl.status_code == 200
        assert dl.content.startswith(b"SQLite format 3\x00")

        # 目录穿越 / 非白名单文件名一律拒绝
        assert client.get(
            "/api/v1/backup/auto/download/..%2F..%2Ftcm_doctor.db", headers=auth_headers,
        ).status_code != 200
        assert client.get(
            "/api/v1/backup/auto/download/other.db", headers=auth_headers,
        ).status_code != 200
    finally:
        auto_backup.save_config(original)
