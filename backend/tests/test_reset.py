"""reset（清空数据）回归测试：清空后内容库不回填，框架基础(账号/字典/腧穴)保留"""
from app.database import SessionLocal
from app.models.herb import Herb
from app.models.knowledge import KnowledgeEntry
from app.models.prescription import ClassicFormula
from app.models.user import User
from app.models.dictionaries import DictionaryTerm
from app.models.acupuncture import Acupoint


def test_reset_clears_content_libs_not_reseeded(client, auth_headers, db_session):
    # 写入几条「自有内容」（与内置不重名），确保 reset 真把它们清掉
    db_session.add(Herb(name="测试药材_RESET"))
    db_session.add(KnowledgeEntry(title="测试条目_RESET", category="条文", content="x"))
    db_session.add(ClassicFormula(name="测试方_RESET", composition={}))
    # 造一条「自有腧穴」，验证 reset 不清空腧穴（框架基础保留）
    db_session.add(Acupoint(name="测试穴_RESET"))
    db_session.commit()

    resp = client.post("/api/v1/backup/reset", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    s = SessionLocal()
    try:
        # 内容库：清空后必须为空（不再回填内置默认）
        assert s.query(Herb).count() == 0
        assert s.query(KnowledgeEntry).count() == 0
        assert s.query(ClassicFormula).count() == 0
        # 框架基础：账号 / 数据字典 / 腧穴 必须保留
        assert s.query(User).filter(User.username == "testadmin").count() == 1
        assert s.query(DictionaryTerm).count() > 0
        # 腧穴为框架基础，reset 后必须保留（本测试写入的腧穴应在）
        assert s.query(Acupoint).filter(Acupoint.name == "测试穴_RESET").count() == 1
    finally:
        s.close()

    # 还原内置数据，避免污染同会话其他测试（共享临时库）
    from app.seed import seed_all

    seed_all()
