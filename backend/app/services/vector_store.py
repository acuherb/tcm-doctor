"""向量存储服务 — ChromaDB 集成（可选依赖）"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ChromaDB 是可选依赖，不可用时降级到关键词检索
_chromadb_available = False
_chroma_client = None
_collection = None

try:
    import chromadb
    _chromadb_available = True
except ImportError:
    logger.info("ChromaDB 未安装，语义检索不可用，降级到关键词检索。安装: pip install chromadb")


def init_chromadb(persist_dir: str = "./chroma_data", embedding_function=None):
    """初始化 ChromaDB；可传入中文 embedding_function 以获得正确的中文语义向量"""
    global _chroma_client, _collection

    if not _chromadb_available:
        return False

    try:
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        _collection = _chroma_client.get_or_create_collection(
            name="tcm_knowledge",
            metadata={"description": "中医知识库向量索引"},
            embedding_function=embedding_function,
        )
        logger.info(f"ChromaDB 初始化成功，当前 { _collection.count()} 条向量")
        return True
    except Exception as e:
        logger.warning(f"ChromaDB 初始化失败: {e}")
        return False


def _try_chinese_embedding(embedding_model: str):
    """尝试构建中文句向量函数（需 sentence-transformers）；失败返回 None"""
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=embedding_model)
    except Exception as e:
        logger.warning(f"中文向量模型不可用，将使用 Chroma 默认英文模型（中文检索效果差）：{e}")
        return None


def bootstrap(persist_dir: str, embedding_model: str, enabled: bool) -> bool:
    """应用启动时调用：按需初始化 Chroma 并返回是否成功（失败时由上层降级到关键词检索）"""
    if not enabled:
        logger.info("语义检索未开启（enable_semantic_search=false），使用关键词检索。")
        return False
    if not _chromadb_available:
        logger.warning(
            "chromadb 未安装，语义检索不可用，降级为关键词检索。"
            "安装: pip install chromadb sentence-transformers"
        )
        return False
    ef = _try_chinese_embedding(embedding_model)
    if ef is None:
        logger.warning("中文向量模型加载失败，语义检索降级（仍可用但中文效果差）。")
    return init_chromadb(persist_dir, ef)


def add_documents(documents: list[dict]):
    """添加文档到向量库

    Args:
        documents: [{"id": str, "title": str, "content": str, "category": str, "metadata": dict}]
    """
    if not _collection:
        logger.warning("ChromaDB 未初始化，跳过文档添加")
        return 0

    ids = []
    texts = []
    metadatas = []

    for doc in documents:
        doc_id = doc.get("id", str(hash(doc.get("title", ""))))
        ids.append(doc_id)
        texts.append(f"{doc.get('title', '')}\n{doc.get('content', '')}")
        metadatas.append({
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "source": doc.get("metadata", {}).get("source", ""),
        })

    try:
        _collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return len(ids)
    except Exception as e:
        logger.error(f"ChromaDB 文档添加失败: {e}")
        return 0


def search(query: str, top_k: int = 5, category: str | None = None) -> list[dict]:
    """语义搜索

    Args:
        query: 搜索查询
        top_k: 返回结果数
        category: 分类过滤

    Returns:
        [{"id", "title", "content", "category", "score"}]
    """
    if not _collection:
        return []

    try:
        where_filter = {"category": category} if category else None
        results = _collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )

        items = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                items.append({
                    "id": doc_id,
                    "title": metadata.get("title", ""),
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "category": metadata.get("category", ""),
                    "score": 1 - distance,  # 简单距离转相似度
                })
        return items
    except Exception as e:
        logger.error(f"ChromaDB 搜索失败: {e}")
        return []


def get_stats() -> dict:
    """获取向量库统计"""
    if not _collection:
        return {"available": False, "count": 0}
    return {
        "available": True,
        "count": _collection.count(),
    }


def rebuild_from_knowledge_db(db_session):
    """从知识库数据库重建向量索引"""
    from app.models.knowledge import KnowledgeEntry

    entries = db_session.query(KnowledgeEntry).all()
    if not entries:
        return 0

    documents = []
    for e in entries:
        documents.append({
            "id": f"entry_{e.id}",
            "title": e.title,
            "content": e.content,
            "category": e.category,
            "metadata": {
                "source": e.source or "",
            },
        })

    return add_documents(documents)


# 注意：不再在此处自动初始化，避免产生空集合误导状态。
# Chroma 的初始化与索引重建统一由 FastAPI lifespan（main.py）按配置调用 bootstrap() 完成。


class VectorStore:
    """向量存储封装"""
    search = staticmethod(search)
    add_documents = staticmethod(add_documents)
    get_stats = staticmethod(get_stats)
    rebuild_from_knowledge_db = staticmethod(rebuild_from_knowledge_db)
    init_chromadb = staticmethod(init_chromadb)


vector_store = VectorStore()
