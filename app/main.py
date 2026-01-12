from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from PIL import Image
import io
import json
import os
from typing import Any, Dict, Tuple

from .llama_client import LlamaClient
from .config import get_settings

app = FastAPI(title="Screenshot Translator", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("app/static/index.html", media_type="text/html")


@app.post("/api/translate")
async def translate(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    # Compatibility: older frontends may still send ctx
    ctx: int | None = Form(None),
):
    try:
        raw = await image.read()
        # Normalize to PNG for predictable base64 size
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=f"Failed to read image: {exc}") from exc

    client = LlamaClient()
    try:
        markdown = await client.translate_image(png_bytes, prompt or None)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await client.aclose()

    _ = ctx  # ignore; server ctx is set at llama-server start
    return JSONResponse({"markdown": markdown})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/api/llama-status")
async def llama_status() -> JSONResponse:
    # 1) ログをざっくり見る
    log_path = "llama-server.log"
    log_status = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-400:]
            text = "\n".join(lines).lower()
            has_loading = "loading model" in text
            has_idle = "idle" in text
            has_listening = "listening" in text or "http server" in text
            has_error = "error" in text

            if has_error:
                log_status = "エラー検出 (ログ)"
            elif has_loading and not has_idle:
                log_status = "モデル読み込み中 (ログより)"
            elif has_idle:
                log_status = "準備完了 (ログより)"
            elif has_listening:
                log_status = "起動中（モデル読み込み未確認）(ログより)"
    except FileNotFoundError:
        log_status = None

    # 2) HTTPで確認
    client = LlamaClient()
    status = await client.get_status()
    await client.aclose()

    # ログが具体的なら優先、HTTPのみならHTTP
    if log_status and status:
        if log_status != status:
            return JSONResponse({"status": f"{log_status} / {status}"})
        return JSONResponse({"status": log_status})
    if log_status:
        return JSONResponse({"status": log_status})
    return JSONResponse({"status": status})


def _read_upload_as_png(file: UploadFile) -> Tuple[bytes, int, int]:
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail=f"Empty upload: {file.filename}")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {file.filename}: {exc}") from exc
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    w, h = img.size
    return buf.getvalue(), w, h


def _extract_first_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("<json>") and text.endswith("</json>"):
        inner = text[len("<json>") : -len("</json>")].strip()
        return json.loads(inner)

    if "```json" in text:
        start = text.find("```json")
        end = text.find("```", start + 7)
        if start != -1 and end != -1 and end > start:
            inner = text[start + 7 : end].strip()
            return json.loads(inner)

    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    brace = 0
    start_idx = None
    for i, ch in enumerate(text):
        if ch == "{":
            if brace == 0:
                start_idx = i
            brace += 1
        elif ch == "}":
            if brace > 0:
                brace -= 1
                if brace == 0 and start_idx is not None:
                    candidate = text[start_idx : i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        continue

    raise ValueError("Could not extract valid JSON from model output")


def _maybe_log_raw_output(raw: str) -> None:
    if os.getenv("OCR_JSON_DEBUG", "0") != "1":
        return
    try:
        path = os.path.join(os.getcwd(), "ocr_json_debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(raw)
            f.write("\n----\n")
    except Exception:
        pass


def _extract_field_from_raw(raw: str, key: str) -> str | None:
    try:
        obj = _extract_first_json(raw)
        val = obj.get(key)
        if isinstance(val, str):
            return val
    except Exception:
        pass

    # Fallback: regex search for a JSON-like "key": "value"
    import re

    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*"(.*?)"', re.DOTALL)
    m = pattern.search(raw)
    if not m:
        return None

    val = m.group(1)
    val = val.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
    return val


def _validate_bbox(b: Dict[str, Any], w: int, h: int) -> Tuple[int, int, int, int]:
    x1 = int(b.get("x1"))
    y1 = int(b.get("y1"))
    x2 = int(b.get("x2"))
    y2 = int(b.get("y2"))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Invalid bbox ordering")
    if x1 < 0 or y1 < 0 or x2 > w or y2 > h:
        raise ValueError("BBox out of image bounds")
    return x1, y1, x2, y2


@app.post("/api/v1/ocr_translate_with_grounding")
async def ocr_translate_with_grounding(
    clean_image: UploadFile = File(...),
    guide_image: UploadFile = File(...),
    options: str = Form(default="{}"),
) -> JSONResponse:
    try:
        opt = json.loads(options) if options else {}
        if not isinstance(opt, dict):
            raise ValueError("options must be JSON object")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid options JSON: {exc}") from exc

    return_roi_fallback = bool(opt.get("return_roi_fallback", True))
    timeout_sec = int(opt.get("timeout_sec", 90))

    clean_png, w, h = _read_upload_as_png(clean_image)
    guide_png, _, _ = _read_upload_as_png(guide_image)
    if w > 1920 or h > 1080:
        raise HTTPException(status_code=400, detail="clean_image exceeds 1920x1080 limit")

    client = LlamaClient()
    try:
        raw = await client.ocr_translate_with_grounding(
            guide_png=guide_png,
            clean_png=clean_png,
            return_roi_fallback=return_roi_fallback,
            timeout_sec=timeout_sec,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await client.aclose()

    try:
        obj = _extract_first_json(raw)
    except Exception as exc:
        _maybe_log_raw_output(raw)
        # Fallback: try to salvage ja_translation/ocr_text from broken JSON
        ja = _extract_field_from_raw(raw, "ja_translation")
        ocr = _extract_field_from_raw(raw, "ocr_text")
        fallback_obj = {
            "target_bbox": {"x1": 0, "y1": 0, "x2": w, "y2": h},
            "ocr_text": ocr or "",
            "ja_translation": (ja or raw).strip(),
            "notes": f"json_parse_failed: {exc}",
        }
        return JSONResponse(fallback_obj)

    try:
        _validate_bbox(obj.get("target_bbox", {}), w=w, h=h)
    except Exception as exc:
        if "roi_fallback" in obj:
            obj["target_bbox"] = {"x1": 0, "y1": 0, "x2": w, "y2": h}
            obj.setdefault("notes", "")
            obj["notes"] = (obj["notes"] + f" | bbox_invalid: {exc}").strip(" |")
        else:
            raise HTTPException(status_code=500, detail=f"Invalid target_bbox: {exc}") from exc

    for key in ("target_bbox", "ocr_text", "ja_translation"):
        if key not in obj:
            raise HTTPException(status_code=500, detail=f"Missing key: {key}")

    return JSONResponse(obj)
