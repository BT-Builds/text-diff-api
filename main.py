import difflib
import re
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import time

app = FastAPI(title="Text Diff API", description="Compare texts and generate unified diffs")

# Rate limiting (simple in-memory)
rate_limit_store: Dict[str, List[float]] = {}
RATE_LIMIT = 100  # requests per minute

security = HTTPBearer(auto_error=False)

def check_rate_limit(api_key: str = None) -> None:
    if api_key is None:
        return
    now = time.time()
    if api_key not in rate_limit_store:
        rate_limit_store[api_key] = []
    rate_limit_store[api_key] = [t for t in rate_limit_store[api_key] if now - t < 60]
    if len(rate_limit_store[api_key]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    rate_limit_store[api_key].append(now)

class DiffRequest(BaseModel):
    text1: str = Field(..., description="First text to compare")
    text2: str = Field(..., description="Second text to compare")
    context: int = Field(3, ge=0, le=100, description="Number of context lines")
    ignore_whitespace: bool = Field(False, description="Ignore whitespace differences")
    ignore_case: bool = Field(False, description="Ignore case differences")

class DiffResponse(BaseModel):
    diff: str
    changes: int
    added_lines: int
    removed_lines: int
    similarity: float

def clean_text(text: str, ignore_whitespace: bool, ignore_case: bool) -> str:
    if ignore_case:
        text = text.lower()
    if ignore_whitespace:
        text = re.sub(r"\s+", " ", text).strip()
    return text

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/compare")
def compare_texts(request: DiffRequest, api_key: Optional[str] = Security(security)):
    check_rate_limit(api_key)
    
    t1 = clean_text(request.text1, request.ignore_whitespace, request.ignore_case)
    t2 = clean_text(request.text2, request.ignore_whitespace, request.ignore_case)
    
    lines1 = t1.splitlines()
    lines2 = t2.splitlines()
    
    # Unified diff
    diff = list(difflib.unified_diff(
        lines1, lines2,
        fromfile="text1", tofile="text2",
        lineterm="",
        n=request.context
    ))
    
    # Calculate stats
    diff_lines = [l for l in diff if l.startswith("+") or l.startswith("-") and not l.startswith("+++")]
    added = len([l for l in diff_lines if l.startswith("+") and not l.startswith("+++")])
    removed = len([l for l in diff_lines if l.startswith("-") and not l.startswith("---")])
    similarity = difflib.SequenceMatcher(None, t1, t2).ratio()
    
    return DiffResponse(
        diff="\n".join(diff),
        changes=len(diff_lines),
        added_lines=added,
        removed_lines=removed,
        similarity=round(similarity * 100, 2)
    )


try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass
