"""
History Lookup Router.
Endpoint:
  GET /api/v1/ta/{code}/history-lookup  → Past similar states & outcomes
For chatbot: "Bu durum geçmişte nasıl sonuçlandı?" queries.
"""
import json
import logging
from fastapi import APIRouter, HTTPException

from app.services.ta_engine import (
    calculate_full_analysis,
    filter_batch_result,
)
from app.core.d1 import get_db, D1Repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ta", tags=["Technical Analysis - History"])


@router.get("/{code}/history-lookup")
async def get_history_lookup(code: str, lookback_bars: int = 20, threshold: float = 5.0):
    """
    Layer: Advanced | Role: Abone/Chatbot
    Finds past occurrences of similar score/regime states and shows outcomes.
    lookback_bars: how many future bars to check for outcome.
    threshold: score tolerance for "similar" state.
    """
    ticker = code.upper()

    # Get current analysis
    full = await calculate_full_analysis(ticker)
    if "error" in full:
        raise HTTPException(status_code=400, detail=full["error"])

    current_score = full.get("score", {}).get("total", 50)
    current_regime = full.get("regime", {}).get("regime", "Unknown")

    # Fetch extended historical data
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="D1 not available")

    repo = D1Repository(db)
    rows = await repo.get_prices(ticker, limit=1000)
    if not rows or len(rows) < 100:
        raise HTTPException(status_code=404, detail="Insufficient historical data")

    rows.reverse()
    closes = [float(r["close"]) for r in rows]

    # Simple heuristic: find past states where score was within threshold
    # and check average forward return
    similar_states = []
    window = 60

    for i in range(window, len(rows) - lookback_bars - 1):
        segment = rows[i - window:i]
        segment_closes = [float(r["close"]) for r in segment]
        if len(segment_closes) < 50:
            continue

        # Approximate score by SMA alignment
        from app.services.indicators import sma
        sma_20 = sma(segment_closes, 20)
        sma_50 = sma(segment_closes, 50)
        score_approx = 50
        if sma_20[-1] is not None and sma_50[-1] is not None:
            if segment_closes[-1] > sma_20[-1]:
                score_approx += 15
            if sma_20[-1] > sma_50[-1]:
                score_approx += 10
            if segment_closes[-1] > sma_50[-1]:
                score_approx += 10
            score_approx = max(0, min(100, score_approx))

        if abs(score_approx - current_score) <= threshold:
            forward_return = (
                (rows[i + lookback_bars]["close"] - rows[i]["close"])
                / rows[i]["close"]
                * 100
            )
            bars_ago = len(rows) - 1 - i
            similar_states.append({
                "date": str(rows[i].get("date", "")),
                "score_approx": score_approx,
                "price": float(rows[i]["close"]),
                "forward_return_pct": round(forward_return, 2),
                "bars_ago": bars_ago,
            })

    if not similar_states:
        return {
            "ticker": ticker,
            "current_score": current_score,
            "current_regime": current_regime,
            "similar_past_states": [],
            "average_outcome": None,
            "positive_outcome_pct": None,
            "sample_size": 0,
        }

    avg_return = sum(s["forward_return_pct"] for s in similar_states) / len(similar_states)
    positive_count = sum(1 for s in similar_states if s["forward_return_pct"] > 0)
    positive_pct = (positive_count / len(similar_states)) * 100

    return {
        "ticker": ticker,
        "current_score": current_score,
        "current_regime": current_regime,
        "similar_past_states": similar_states[:10],
        "average_outcome": round(avg_return, 2),
        "positive_outcome_pct": round(positive_pct, 1),
        "sample_size": len(similar_states),
    }
