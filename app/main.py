import base64
import io
import os

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

app = FastAPI(title="InstaPrep")

# ---- Formati di ritaglio (larghezza x altezza in px, Instagram-friendly) ----
FORMATS = {
    "post_4_5": (1080, 1350),   # Post feed 4:5
    "story_9_16": (1080, 1920), # Storia 9:16
}


def crop_to_ratio(img: Image.Image, target_w: int, target_h: int,
                  fx=None, fy=None) -> Image.Image:
    """Ritaglia al rapporto voluto e ridimensiona alla dimensione target.

    fx, fy sono il punto focale in coordinate normalizzate (0..1) rispetto
    all'immagine: il ritaglio viene centrato su quel punto, entro i bordi.
    Se fx/fy sono None si usa il centro (0.5), cioè centraggio automatico.
    """
    img = ImageOps.exif_transpose(img)  # rispetta orientamento EXIF
    target_ratio = target_w / target_h
    w, h = img.size
    current_ratio = w / h

    fx = 0.5 if fx is None else max(0.0, min(1.0, fx))
    fy = 0.5 if fy is None else max(0.0, min(1.0, fy))

    if current_ratio > target_ratio:
        # troppo larga -> taglia i lati, centra sul punto in orizzontale
        new_w = int(h * target_ratio)
        left = int(fx * w - new_w / 2)
        left = max(0, min(left, w - new_w))
        img = img.crop((left, 0, left + new_w, h))
    else:
        # troppo alta -> taglia sopra/sotto, centra sul punto in verticale
        new_h = int(w / target_ratio)
        top = int(fy * h - new_h / 2)
        top = max(0, min(top, h - new_h))
        img = img.crop((0, top, w, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def apply_adjustments(img: Image.Image, auto: bool,
                      brightness: float, contrast: float,
                      saturation: float, sharpness: float) -> Image.Image:
    """auto=True applica autocontrast; poi applica i moltiplicatori manuali (1.0 = invariato)."""
    if auto:
        img = ImageOps.autocontrast(img, cutoff=1)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img


def img_to_b64(img: Image.Image) -> str:
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


@app.post("/api/process")
async def process(
    file: UploadFile = File(...),
    auto: bool = Form(True),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    sharpness: float = Form(1.0),
    # punto focale in coordinate 0..1; -1 = non impostato (centraggio automatico)
    focus_x: float = Form(-1.0),
    focus_y: float = Form(-1.0),
):
    raw = await file.read()
    base = Image.open(io.BytesIO(raw))
    base = ImageOps.exif_transpose(base)
    base = apply_adjustments(base, auto, brightness, contrast, saturation, sharpness)

    fx = None if focus_x < 0 else focus_x
    fy = None if focus_y < 0 else focus_y

    out = {}
    for name, (tw, th) in FORMATS.items():
        cropped = crop_to_ratio(base, tw, th, fx, fy)
        out[name] = img_to_b64(cropped)

    # rimando anche le dimensioni originali, servono al frontend per i riquadri
    return JSONResponse({"images": out, "orig_w": base.width, "orig_h": base.height})


@app.post("/api/caption")
async def caption(
    description: str = Form(...),
    tone: str = Form("coinvolgente e naturale"),
    language: str = Form("italiano"),
):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(
            {"error": "ANTHROPIC_API_KEY non configurata"}, status_code=500
        )

    prompt = (
        f"Scrivi una caption per un post Instagram interamente in {language}, "
        f"con tono {tone}, a partire da questa descrizione:\n\n"
        f'"{description}"\n\n'
        f"IMPORTANTE: caption e hashtag devono essere scritti in {language}, "
        "senza mescolare altre lingue.\n\n"
        "Restituisci:\n"
        "1. Una caption breve e curata (2-4 righe), con eventuali emoji misurate.\n"
        "2. Una riga vuota.\n"
        "3. Da 12 a 20 hashtag pertinenti e mirati (mix di popolari e di nicchia), "
        "tutti su una riga, separati da spazio.\n"
        "Non aggiungere altro testo o spiegazioni."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 700,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

    if r.status_code != 200:
        return JSONResponse({"error": r.text}, status_code=r.status_code)

    data = r.json()
    text = "".join(
        block.get("text", "") for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()
    return JSONResponse({"caption": text})


# frontend statico (montato per ultimo così le /api restano prioritarie)
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
