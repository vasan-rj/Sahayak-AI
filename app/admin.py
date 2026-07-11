"""Admin API — manage form templates, parse uploaded blank forms, review sessions.

No auth (localhost demo, stated limitation): these routes expose template editing
and applicants' capture logs (which contain names / ID values read from documents).
Do not expose this port on a shared network.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from .form_parser import FormParseError, parse_blank_form
from .session import _default_log_dir
from .template_store import TemplateError, get_store
from .witness_log import WitnessLog, WitnessLogError

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Templates ----------------------------------------------------------------
@router.get("/templates")
async def list_templates() -> list[dict]:
    return get_store().list_templates()


@router.get("/templates/{tid}")
async def get_template(tid: str) -> dict:
    try:
        return get_store().get(tid)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown template")


@router.post("/templates")
async def create_template(template: dict = Body(...)) -> dict:
    try:
        return get_store().save(template)
    except TemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/templates/{tid}")
async def update_template(tid: str, template: dict = Body(...)) -> dict:
    template["template_id"] = tid  # the path id wins over the body
    try:
        return get_store().save(template)
    except TemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/templates/{tid}")
async def delete_template(tid: str) -> dict:
    get_store().delete(tid)
    return {"ok": True}


@router.post("/templates/{tid}/activate")
async def activate_template(tid: str) -> dict:
    try:
        get_store().set_active(tid)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown template")
    return {"active": tid}


# --- Upload a blank form -> draft field-map -----------------------------------
@router.post("/parse-form")
async def parse_form(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    mime = file.content_type or "image/jpeg"
    try:
        # generate_content is sync; keep it off the event loop.
        return await asyncio.to_thread(parse_blank_form, data, mime)
    except FormParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- Sessions / capture logs --------------------------------------------------
def _log_dir() -> str:
    return _default_log_dir()


@router.get("/sessions")
async def list_sessions() -> list[dict]:
    directory = _log_dir()
    out: list[dict] = []
    if os.path.isdir(directory):
        for fn in os.listdir(directory):
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(directory, fn)
            log = WitnessLog(path)
            try:
                entries = log.read()
            except WitnessLogError:
                entries = []
            out.append(
                {
                    "id": fn[:-6],
                    "entries": len(entries),
                    "fields": sum(1 for e in entries if e.get("kind") == "field_captured"),
                    "complete": any(e.get("kind") == "form_complete" for e in entries),
                    "mtime": os.path.getmtime(path),
                }
            )
    out.sort(key=lambda s: s["mtime"], reverse=True)
    return out


@router.get("/sessions/{sid}")
async def get_session(sid: str) -> dict:
    path = os.path.join(_log_dir(), f"{sid}.jsonl")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="unknown session")
    log = WitnessLog(path)
    try:
        entries = log.read()
        verified = log.verify()
    except WitnessLogError as exc:
        raise HTTPException(status_code=422, detail=f"corrupt capture log: {exc}")
    return {"id": sid, "entries": entries, "verified": verified}
