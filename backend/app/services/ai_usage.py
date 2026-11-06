"""AI 用量采集与成本估算。

单价从 settings 读取（系统设置可改，持久化到 .env），单位为「元 / 百万 tokens」。
DeepSeek 对命中缓存的输入 token 单独计价，故区分 cache_hit / cache_miss；
第三方 Vision 端点通常不返回缓存细分，按输入 / 输出两档计价。
所有单价默认为 0（未配置）：此时仍完整统计 token 与调用次数，只是费用显示 0。
"""
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.ai_usage import AiUsageLog

logger = logging.getLogger(__name__)


def get_pricing() -> dict[str, float]:
    """当前单价（元 / 百万 tokens）。"""
    return {
        "input": float(settings.ai_price_input_per_m or 0),
        "cache_hit": float(settings.ai_price_cache_hit_per_m or 0),
        "output": float(settings.ai_price_output_per_m or 0),
        "vision_input": float(settings.ai_price_vision_input_per_m or 0),
        "vision_output": float(settings.ai_price_vision_output_per_m or 0),
    }


def pricing_configured() -> bool:
    return any(v > 0 for v in get_pricing().values())


def calc_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int,
    is_vision: bool,
    pricing: dict[str, float] | None = None,
) -> float:
    """按单价估算单次费用（元）。"""
    p = pricing or get_pricing()
    if is_vision:
        return (
            prompt_tokens * p["vision_input"] + completion_tokens * p["vision_output"]
        ) / 1_000_000
    cache_hit = min(cache_hit_tokens, prompt_tokens)
    cache_miss = prompt_tokens - cache_hit
    return (
        cache_hit * p["cache_hit"]
        + cache_miss * p["input"]
        + completion_tokens * p["output"]
    ) / 1_000_000


def parse_usage(usage: dict | None) -> dict[str, int]:
    """把上游 usage 归一化为内部字段；缺失字段按 0 / 可推导值处理。"""
    u = usage or {}

    def _int(key: str) -> int:
        try:
            return max(0, int(u.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    prompt = _int("prompt_tokens")
    completion = _int("completion_tokens")
    total = _int("total_tokens") or (prompt + completion)
    hit = _int("prompt_cache_hit_tokens")
    miss = _int("prompt_cache_miss_tokens")
    if "prompt_cache_miss_tokens" not in u:
        miss = max(0, prompt - hit)  # 上游未给缓存细分时，全部输入按未命中计
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
    }


def record_ai_usage(
    *,
    scene: str = "",
    model: str = "",
    is_vision: bool = False,
    usage: dict | None = None,
    user_id: int | None = None,
    username: str | None = None,
    success: bool = True,
    error: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """记录一次 AI 调用。独立会话、写失败绝不影响主流程（AI 问诊照常返回）。"""
    try:
        t = parse_usage(usage)
        cost = calc_cost(
            t["prompt_tokens"], t["completion_tokens"], t["cache_hit_tokens"], is_vision
        ) if success else 0.0
        db: Session = SessionLocal()
        try:
            db.add(
                AiUsageLog(
                    user_id=user_id,
                    username=username,
                    scene=scene,
                    model=model,
                    is_vision=is_vision,
                    prompt_tokens=t["prompt_tokens"],
                    completion_tokens=t["completion_tokens"],
                    total_tokens=t["total_tokens"],
                    cache_hit_tokens=t["cache_hit_tokens"],
                    cache_miss_tokens=t["cache_miss_tokens"],
                    cost=cost,
                    success=success,
                    error=(error or None)[:200] if error else None,
                    duration_ms=duration_ms,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.warning("AI 用量记录失败（不影响主流程）: %s", e)
