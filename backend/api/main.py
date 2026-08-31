"""TruthLens FastAPI application."""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend import storage
from backend.analysis.engine import load_dataframe, full_scan_payload
from backend.reports.html_report import generate_html_report
from backend.reports.pdf_report import generate_pdf_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("truthlens.api")

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_PATH = ROOT / "datasets" / "examples" / "suspicious_sales.xlsx"

app = FastAPI(
    title="TruthLens API",
    description="Data Forensics & Statistical Integrity Engine",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

MAX_SIZE = 50 * 1024 * 1024  # 50 MB

# initialize storage at import time so the DB is always available
storage.init_db()


@app.on_event("startup")
def _startup() -> None:
    storage.init_db()
    logger.info("TruthLens API ready")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "truthlens", "version": "1.0.0"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    if len(raw) > MAX_SIZE:
        raise HTTPException(413, "文件超过 50MB 限制")
    if not raw:
        raise HTTPException(400, "上传文件为空")
    try:
        df = load_dataframe(raw, file.filename or "upload")
    except Exception as e:
        raise HTTPException(400, f"无法解析文件: {e}")
    if df.empty:
        raise HTTPException(400, "数据表为空")
    payload = full_scan_payload(df, file.filename or "upload")
    storage.save_scan(payload)
    return payload


@app.get("/api/demo")
def demo() -> dict:
    """Run the bundled suspicious_sales.xlsx demo dataset."""
    if not DEMO_PATH.exists():
        raise HTTPException(404, "Demo dataset not found")
    raw = DEMO_PATH.read_bytes()
    df = load_dataframe(raw, DEMO_PATH.name)
    payload = full_scan_payload(df, DEMO_PATH.name)
    storage.save_scan(payload)
    return payload


@app.get("/api/analyses")
def analyses(limit: int = 50) -> list[dict]:
    return storage.list_scans(limit)


@app.get("/api/analyses/{scan_id}")
def get_analysis(scan_id: str) -> dict:
    result = storage.get_scan(scan_id)
    if result is None:
        raise HTTPException(404, "分析记录不存在")
    return result


@app.get("/api/analyses/{scan_id}/report")
def get_report(scan_id: str, format: str = "html") -> Response:
    result = storage.get_scan(scan_id)
    if result is None:
        raise HTTPException(404, "分析记录不存在")
    fmt = format.lower()
    if fmt == "json":
        return Response(
            content=json.dumps(result, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="truthlens_{scan_id}.json"'},
        )
    if fmt == "pdf":
        try:
            pdf_bytes = generate_pdf_report(result)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="truthlens_{scan_id}.pdf"'},
            )
        except Exception as e:
            logger.exception("PDF generation failed")
            raise HTTPException(500, f"PDF 生成失败: {e}")
    return HTMLResponse(
        content=generate_html_report(result),
        headers={"Content-Disposition": f'inline; filename="truthlens_{scan_id}.html"'},
    )
