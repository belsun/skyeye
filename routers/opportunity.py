from fastapi import APIRouter, Query, HTTPException

router = APIRouter()


@router.get("/opportunity-radar")
def get_opportunity_radar(
    market: str = Query("all", pattern="^(all|hk|us)$"),
    lookback_days: int = Query(10, ge=3, le=45),
    mode: str = Query("balanced", pattern="^(balanced)$"),
):
    try:
        from ml.opportunity import build_opportunity_radar

        return build_opportunity_radar(market=market, lookback_days=lookback_days, mode=mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
