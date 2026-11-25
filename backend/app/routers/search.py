from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai_search, config
from ..db import get_db
from ..models import Variety
from ..schemas import VarietyOut
from .public import list_varieties

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchStatus(BaseModel):
    enabled: bool
    ready: bool


class SearchResult(BaseModel):
    mode: str          # "ai" — the model picked; "name" — the regular search by name answered
    status: str        # found | none | clarify
    items: list[VarietyOut]
    fallback: bool     # the AI was asked but could not answer, so the regular search answered


@router.get("/status", response_model=SearchStatus)
def search_status():
    """The widget shows the smart-search button only when the model is ready."""
    return SearchStatus(enabled=config.AI_SEARCH_ENABLED, ready=ai_search.model_ready())


@router.get("", response_model=SearchResult)
def smart_search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    q = q.strip()[:ai_search.MAX_QUERY]  # long input is cut, not rejected
    if not q:
        return SearchResult(mode="name", status="clarify", items=[], fallback=False)
    varieties = list(db.scalars(select(Variety).where(Variety.is_active.is_(True)).order_by(Variety.id)))
    try:
        status, ids = ai_search.pick(q, varieties)
    except ai_search.AISearchError:
        items = list_varieties(q=q, type=None, color=[], in_stock=False, sort="default", db=db)
        return SearchResult(mode="name", status="found" if items else "none", items=items,
                            fallback=config.AI_SEARCH_ENABLED)
    by_id = {v.id: v for v in varieties}
    return SearchResult(mode="ai", status=status, items=[VarietyOut.from_model(by_id[i]) for i in ids], fallback=False)
