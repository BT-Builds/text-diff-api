import difflib
import re
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import time

app = FastAPI(title="Text Diff API", description="Compare texts and generate unified diffs")
# === BT Builds Standard Middleware (auto-injected) ===
from fastapi.middleware.cors import CORSMiddleware as _BTCors
app.add_middleware(_BTCors, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], expose_headers=["X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset"])

@app.middleware("http")
async def _bt_add_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "btbuilds"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


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

def do_compare(text1: str, text2: str, context: int, ignore_whitespace: bool, ignore_case: bool) -> DiffResponse:
    """Core comparison logic extracted for reuse"""
    t1 = clean_text(text1, ignore_whitespace, ignore_case)
    t2 = clean_text(text2, ignore_whitespace, ignore_case)
    
    lines1 = t1.splitlines()
    lines2 = t2.splitlines()
    
    # Unified diff
    diff = list(difflib.unified_diff(
        lines1, lines2,
        fromfile="text1", tofile="text2",
        lineterm="",
        n=context
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

# Bulk request/response models
class BulkCompareRequestItem(BaseModel):
    text1: str = Field(..., description="First text to compare")
    text2: str = Field(..., description="Second text to compare")
    context: int = Field(3, ge=0, le=100, description="Number of context lines")
    ignore_whitespace: bool = Field(False, description="Ignore whitespace differences")
    ignore_case: bool = Field(False, description="Ignore case differences")

class BulkCompareRequest(BaseModel):
    items: List[BulkCompareRequestItem] = Field(..., max_items=1000, description="Up to 1000 comparisons")

class BulkCompareResultItem(BaseModel):
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    error: Optional[str]

class BulkCompareResponse(BaseModel):
    results: List[BulkCompareResultItem]
    total: int
    successful: int

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/compare")
def compare_texts(request: DiffRequest, api_key: Optional[str] = Security(security)):
    check_rate_limit(api_key)
    return do_compare(request.text1, request.text2, request.context, request.ignore_whitespace, request.ignore_case)

@app.post("/bulk/compare")
def bulk_compare(request: BulkCompareRequest, api_key: Optional[str] = Security(security)):
    check_rate_limit(api_key)
    
    results: List[BulkCompareResultItem] = []
    successful = 0
    
    for item in request.items:
        try:
            output = do_compare(item.text1, item.text2, item.context, item.ignore_whitespace, item.ignore_case)
            results.append(BulkCompareResultItem(input=item.model_dump(), output=output.model_dump(), error=None))
            successful += 1
        except Exception as e:
            results.append(BulkCompareResultItem(input=item.model_dump(), output=None, error=str(e)))
    
    return BulkCompareResponse(results=results, total=len(request.items), successful=successful)

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass