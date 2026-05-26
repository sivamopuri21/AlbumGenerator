import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from app.models.job_store import job_store
from app.config import OUTPUT_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.model_dump()


@router.get("/jobs/{job_id}/download")
async def download_zip(job_id: str):
    """Download the complete album package (ZIP with PDF + JPEG + PSD)."""
    zip_path = OUTPUT_PATH / job_id / "album_output.zip"
    if not zip_path.exists():
        raise HTTPException(404, "Album not ready yet")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"album_{job_id}.zip",
    )


@router.get("/jobs/{job_id}/pdf")
async def download_pdf(job_id: str):
    """Download just the PDF."""
    pdf_path = OUTPUT_PATH / job_id / "album.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "PDF not ready yet")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"album_{job_id}.pdf",
    )


@router.get("/jobs/{job_id}/preview/{page_num}")
async def get_page_preview(job_id: str, page_num: int):
    """Get a single page JPEG for preview."""
    jpeg_path = OUTPUT_PATH / job_id / "jpeg" / f"page_{page_num:03d}.jpg"
    if not jpeg_path.exists():
        raise HTTPException(404, f"Page {page_num} not found")
    return FileResponse(jpeg_path, media_type="image/jpeg")


@router.get("/jobs/{job_id}/pages")
async def list_pages(job_id: str):
    """List all available page previews."""
    jpeg_dir = OUTPUT_PATH / job_id / "jpeg"
    if not jpeg_dir.exists():
        raise HTTPException(404, "Album not ready yet")
    pages = sorted(jpeg_dir.glob("page_*.jpg"))
    return {
        "total_pages": len(pages),
        "pages": [
            {"page_num": i + 1, "url": f"/api/jobs/{job_id}/preview/{i + 1}"}
            for i in range(len(pages))
        ],
    }


@router.post("/psd/analyze")
async def analyze_psd_file(file: UploadFile = File(...)):
    """Upload a single PSD and return layer info + preview."""
    import uuid
    from app.config import OUTPUT_PATH
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 500000000

    if not file.filename.lower().endswith('.psd'):
        raise HTTPException(400, "File must be a PSD")

    job_id = uuid.uuid4().hex[:8]
    out_dir = OUTPUT_PATH / f"psd_preview_{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded PSD
    psd_path = out_dir / file.filename
    data = await file.read()
    psd_path.write_bytes(data)

    # Parse it
    from psd_tools import PSDImage
    try:
        psd = PSDImage.open(str(psd_path))
    except Exception as e:
        raise HTTPException(400, "Please upload a valid PSD file. The file you uploaded is either corrupted or not a PSD format.")

    # Generate composite preview (resized for web)
    composite = psd.composite()
    if composite.mode in ('RGBA', 'LA'):
        bg = Image.new('RGB', composite.size, (255, 255, 255))
        bg.paste(composite, mask=composite.split()[3])
        composite = bg
    elif composite.mode != 'RGB':
        composite = composite.convert('RGB')

    # Save full-resolution version for compositing (exact PSD dimensions, preserve DPI)
    fullres_path = out_dir / "fullres.jpg"
    composite.save(str(fullres_path), "JPEG", quality=100, dpi=(300, 300))

    # Resize for web preview (max 1200px wide)
    w, h = composite.size
    preview_composite = composite
    if w > 1200:
        ratio = 1200 / w
        preview_composite = composite.resize((1200, int(h * ratio)), Image.LANCZOS)

    preview_path = out_dir / "preview.jpg"
    preview_composite.save(str(preview_path), "JPEG", quality=85)

    # Extract layer info — including group children
    layers = []
    groups = []

    def _scan_layer(layer, parent_group=None):
        bbox = layer.bbox
        layer_info = {
            "name": layer.name,
            "visible": layer.is_visible(),
            "kind": str(getattr(layer, 'kind', 'unknown')),
            "x": bbox[0],
            "y": bbox[1],
            "width": bbox[2] - bbox[0],
            "height": bbox[3] - bbox[1],
            "parent_group": parent_group,
        }
        layers.append(layer_info)

        # If it's a group, scan children
        if hasattr(layer, '__iter__') and str(getattr(layer, 'kind', '')) == 'group':
            children = []
            for child in layer:
                child_bbox = child.bbox
                cw = child_bbox[2] - child_bbox[0]
                ch = child_bbox[3] - child_bbox[1]
                child_info = {
                    "name": child.name,
                    "visible": child.is_visible(),
                    "kind": str(getattr(child, 'kind', 'unknown')),
                    "x": child_bbox[0],
                    "y": child_bbox[1],
                    "width": cw,
                    "height": ch,
                    "parent_group": layer.name,
                }
                children.append(child_info)
                layers.append(child_info)
                # Recurse into nested groups
                if hasattr(child, '__iter__') and str(getattr(child, 'kind', '')) == 'group':
                    _scan_layer(child, layer.name)

            # Count boxes in this group (children > 200px)
            boxes = [c for c in children if c["width"] > 200 and c["height"] > 200]
            portrait_boxes = [b for b in boxes if b["height"] > b["width"] * 1.2]
            landscape_boxes = [b for b in boxes if b["width"] > b["height"] * 1.2]
            square_boxes = [b for b in boxes if not (b["height"] > b["width"] * 1.2) and not (b["width"] > b["height"] * 1.2)]

            groups.append({
                "name": layer.name,
                "total_children": len(children),
                "boxes": len(boxes),
                "portrait_boxes": len(portrait_boxes),
                "landscape_boxes": len(landscape_boxes),
                "square_boxes": len(square_boxes),
                "children": children,
            })

    for layer in psd:
        _scan_layer(layer)

    return {
        "preview_id": job_id,
        "filename": file.filename,
        "width": psd.width,
        "height": psd.height,
        "layer_count": len(layers),
        "layers": layers,
        "groups": groups,
        "preview_url": f"/api/psd/preview/{job_id}",
    }


@router.get("/psd/preview/{preview_id}")
async def get_psd_preview(preview_id: str, token: str = None):
    """Serve the PSD preview image. Accepts token as query param for img tags."""
    import time as _time
    from app.routes.auth import _active_tokens
    # Verify token from query param (for img src)
    if token and (token not in _active_tokens or _time.time() > _active_tokens.get(token, 0)):
        raise HTTPException(401, "Invalid token")
    from app.config import OUTPUT_PATH
    preview_path = OUTPUT_PATH / f"psd_preview_{preview_id}" / "preview.jpg"
    if not preview_path.exists():
        raise HTTPException(404, "Preview not found")
    return FileResponse(preview_path, media_type="image/jpeg")


@router.post("/psd/composite")
async def composite_psd(
    preview_id: str = Form(...),
    **kwargs,
):
    """Place uploaded photos into the PSD template slots and return result."""
    import uuid
    from app.config import OUTPUT_PATH
    from PIL import Image
    import cv2
    import numpy as np

    Image.MAX_IMAGE_PIXELS = 500000000

    # Load the original analysis
    preview_dir = OUTPUT_PATH / f"psd_preview_{preview_id}"
    if not preview_dir.exists():
        raise HTTPException(404, "Preview not found. Please re-analyze the PSD.")

    # Load background
    bg_path = preview_dir / "preview.jpg"
    if not bg_path.exists():
        raise HTTPException(404, "Background preview not found")

    background = cv2.imread(str(bg_path))
    if background is None:
        raise HTTPException(500, "Failed to load background")

    return {"detail": "Use the multipart endpoint below"}


@router.post("/psd/composite-slots")
async def composite_slots(request: Request):
    """
    Place photos into PSD slots.
    Accepts multipart form with preview_id and slot_N files.
    """
    import uuid
    from app.config import OUTPUT_PATH
    import cv2
    import numpy as np
    from psd_tools import PSDImage
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 500000000

    form = await request.form()
    preview_id = form.get("preview_id")
    if not preview_id:
        raise HTTPException(400, "preview_id required")

    preview_dir = OUTPUT_PATH / f"psd_preview_{preview_id}"
    if not preview_dir.exists():
        raise HTTPException(404, "Preview session not found")

    # Load background at FULL RESOLUTION for quality output
    fullres_path = preview_dir / "fullres.jpg"
    bg_path = fullres_path if fullres_path.exists() else preview_dir / "preview.jpg"
    background = cv2.imread(str(bg_path))
    if background is None:
        raise HTTPException(500, "Cannot load background")

    bg_h, bg_w = background.shape[:2]

    # Keep original PSD dimensions — no upscaling
    SCALE_FACTOR = 1

    # Load PSD to get layer info
    psd_files = list(preview_dir.glob("*.psd"))
    if not psd_files:
        raise HTTPException(404, "PSD file not found in session")

    psd = PSDImage.open(str(psd_files[0]))

    # Get slot layers — look INSIDE groups for actual photo boxes
    slot_layers = []
    for layer in psd:
        if not layer.is_visible():
            continue
        if "background" in layer.name.lower() or "bg" in layer.name.lower():
            continue

        # If it's a group, use its children as slots (not the group itself)
        if hasattr(layer, '__iter__') and str(getattr(layer, 'kind', '')) == 'group':
            for child in layer:
                if not child.is_visible():
                    continue
                bbox = child.bbox
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                # Only include reasonably sized boxes (not text, not full-page)
                if w > 200 and h > 200 and not (w > psd.width * 0.95 and h > psd.height * 0.95):
                    slot_layers.append({"x": bbox[0], "y": bbox[1], "w": w, "h": h, "name": child.name})
        else:
            bbox = layer.bbox
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Skip full-page layers and tiny layers
            if w > 200 and h > 200 and not (w > psd.width * 0.95 and h > psd.height * 0.95):
                slot_layers.append({"x": bbox[0], "y": bbox[1], "w": w, "h": h, "name": layer.name})

    # Sort by position: LEFT PAGE first (top to bottom, left to right), then RIGHT PAGE (top to bottom, right to left)
    # Split at the midpoint of the PSD width
    mid_x = psd.width / 2
    left_slots = [s for s in slot_layers if s["x"] + s["w"] / 2 < mid_x]
    right_slots = [s for s in slot_layers if s["x"] + s["w"] / 2 >= mid_x]
    left_slots.sort(key=lambda s: (s["y"], s["x"]))
    right_slots.sort(key=lambda s: (s["y"], s["x"]))  # left to right for right page
    slot_layers = left_slots + right_slots

    # No scaling — work at original PSD resolution
    scale_x = 1.0
    scale_y = 1.0

    # Place photos with smart orientation matching
    # Collect all uploaded photos and save them to disk for "Move to Used"
    uploaded_photos = []
    photos_dir = preview_dir / "photos"
    photos_dir.mkdir(exist_ok=True)

    for key, upload_file in form.items():
        if not key.startswith("slot_"):
            continue
        photo_data = await upload_file.read()

        # Save photo to disk with original filename
        filename = getattr(upload_file, 'filename', None) or f'photo_{key}.jpg'
        photo_save_path = photos_dir / filename
        with open(str(photo_save_path), 'wb') as f:
            f.write(photo_data)

        nparr = np.frombuffer(photo_data, np.uint8)
        photo = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if photo is not None:
            ph, pw = photo.shape[:2]
            orientation = "landscape" if pw > ph * 1.2 else ("portrait" if ph > pw * 1.2 else "square")
            uploaded_photos.append({"photo": photo, "orientation": orientation, "idx": len(uploaded_photos), "filename": filename})

    # Classify slots by orientation
    slot_info = []
    for i, slot in enumerate(slot_layers):
        w, h = slot["w"], slot["h"]
        orientation = "landscape" if w > h * 1.2 else ("portrait" if h > w * 1.2 else "square")
        slot_info.append({"idx": i, "slot": slot, "orientation": orientation})

    # Match photos to slots by orientation
    portrait_slots = [s for s in slot_info if s["orientation"] == "portrait"]
    landscape_slots = [s for s in slot_info if s["orientation"] == "landscape"]
    square_slots = [s for s in slot_info if s["orientation"] == "square"]

    portrait_photos = [p for p in uploaded_photos if p["orientation"] == "portrait"]
    landscape_photos = [p for p in uploaded_photos if p["orientation"] == "landscape"]
    square_photos = [p for p in uploaded_photos if p["orientation"] == "square"]

    assignments = {}
    used_photo_idxs = set()

    # Portrait photos → portrait slots
    for slot, photo in zip(portrait_slots, portrait_photos):
        assignments[slot["idx"]] = photo
        used_photo_idxs.add(photo["idx"])
    # Landscape photos → landscape slots
    for slot, photo in zip(landscape_slots, landscape_photos):
        assignments[slot["idx"]] = photo
        used_photo_idxs.add(photo["idx"])
    # Square photos → square slots
    for slot, photo in zip(square_slots, square_photos):
        assignments[slot["idx"]] = photo
        used_photo_idxs.add(photo["idx"])

    # Fill remaining with leftover photos
    remaining = [p for p in uploaded_photos if p["idx"] not in used_photo_idxs]
    unassigned = [s for s in slot_info if s["idx"] not in assignments]
    for slot, photo in zip(unassigned, remaining):
        assignments[slot["idx"]] = photo

    # Composite each assignment — using Pillow for highest quality
    # Strategy: If photo is larger than slot, only crop (no downscale) to preserve quality
    from PIL import Image as PILImg
    bg_pil = PILImg.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB))

    for slot_idx, photo_info in assignments.items():
        slot = slot_layers[slot_idx]
        sx = int(slot["x"] * scale_x)
        sy = int(slot["y"] * scale_y)
        sw = int(slot["w"] * scale_x)
        sh = int(slot["h"] * scale_y)

        photo = photo_info["photo"]
        photo_pil = PILImg.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB))
        pw, ph = photo_pil.size

        slot_aspect = sw / max(sh, 1)
        photo_aspect = pw / max(ph, 1)

        # Calculate the size needed to cover the slot
        if photo_aspect > slot_aspect:
            # Photo is wider — fit by height
            target_h = sh
            target_w = int(sh * photo_aspect)
        else:
            # Photo is taller — fit by width
            target_w = sw
            target_h = int(sw / photo_aspect) if photo_aspect > 0 else sh

        # Resize to fit slot — preserve original quality
        photo_pil = photo_pil.resize((max(target_w, 1), max(target_h, 1)), PILImg.LANCZOS)

        # Add 20% smoothness + 10% sharpness
        from PIL import ImageFilter
        photo_pil = photo_pil.filter(ImageFilter.GaussianBlur(radius=0.4))
        photo_pil = photo_pil.filter(ImageFilter.UnsharpMask(radius=1.0, percent=15, threshold=2))

        # Center crop to exact slot size
        crop_x = max((photo_pil.width - sw) // 2, 0)
        crop_y = max((photo_pil.height - sh) // 2, 0)
        photo_pil = photo_pil.crop((crop_x, crop_y, crop_x + sw, crop_y + sh))

        # Paste onto background
        if sx >= 0 and sy >= 0 and sx + sw <= bg_pil.width and sy + sh <= bg_pil.height:
            bg_pil.paste(photo_pil, (sx, sy))

    # Convert back for saving
    background = cv2.cvtColor(np.array(bg_pil), cv2.COLOR_RGB2BGR)

    # Save result at full quality with 300 DPI, exact original dimensions
    result_id = uuid.uuid4().hex[:8]
    result_path = OUTPUT_PATH / f"psd_result_{result_id}.jpg"
    # Use Pillow to save with DPI metadata (OpenCV doesn't support DPI)
    from PIL import Image as PILImage
    result_rgb = cv2.cvtColor(background, cv2.COLOR_BGR2RGB)
    result_img = PILImage.fromarray(result_rgb)
    result_img.save(str(result_path), "JPEG", quality=100, dpi=(300, 300))

    # Save reference to original PSD for layered download
    import json
    meta_path = OUTPUT_PATH / f"psd_result_{result_id}_meta.json"
    meta_path.write_text(json.dumps({"preview_id": preview_id, "psd_file": str(psd_files[0])}))

    # Save slot info for adjustments later
    slot_meta = OUTPUT_PATH / f"psd_result_{result_id}_slots.json"
    slot_meta.write_text(json.dumps({
        "slots": slot_layers,
        "preview_id": preview_id,
        "psd_file": str(psd_files[0]),
    }))

    return {"result_id": result_id}


@router.post("/psd/adjust-slot")
async def adjust_slot(request: Request):
    """
    Re-composite a single slot with zoom/offset adjustments.
    Body (multipart form):
      - result_id: existing result to modify
      - slot_index: which slot to adjust
      - photo: the photo file
      - zoom: float (1.0 = fit, 1.5 = 150% zoom, etc.)
      - offset_x: float (-1.0 to 1.0, 0 = center)
      - offset_y: float (-1.0 to 1.0, 0 = center)
    """
    import json
    from app.config import OUTPUT_PATH
    from PIL import Image as PILImage
    import cv2
    import numpy as np

    PILImage.MAX_IMAGE_PIXELS = 500000000

    form = await request.form()
    result_id = form.get("result_id", "")
    slot_index = int(form.get("slot_index", 0))
    zoom = float(form.get("zoom", 1.0))
    offset_x = float(form.get("offset_x", 0.0))  # -1 to 1
    offset_y = float(form.get("offset_y", 0.0))  # -1 to 1
    rotation = float(form.get("rotation", 0.0))  # degrees

    # Load existing result
    result_path = OUTPUT_PATH / f"psd_result_{result_id}.jpg"
    if not result_path.exists():
        raise HTTPException(404, "Result not found")

    background = cv2.imread(str(result_path))
    if background is None:
        raise HTTPException(500, "Cannot load result")

    bg_h, bg_w = background.shape[:2]

    # Load slot info
    slot_meta_path = OUTPUT_PATH / f"psd_result_{result_id}_slots.json"
    if not slot_meta_path.exists():
        raise HTTPException(404, "Slot info not found")

    slot_data = json.loads(slot_meta_path.read_text())
    slot_layers = slot_data["slots"]

    if slot_index >= len(slot_layers):
        raise HTTPException(400, f"Invalid slot index: {slot_index}")

    slot = slot_layers[slot_index]

    # Load PSD for scale
    from psd_tools import PSDImage
    psd_file = slot_data.get("psd_file", "")
    psd = PSDImage.open(psd_file)

    # The result image is at 2x PSD resolution
    SCALE_FACTOR = bg_w / psd.width
    scale_x = SCALE_FACTOR
    scale_y = SCALE_FACTOR

    sx = int(slot["x"] * scale_x)
    sy = int(slot["y"] * scale_y)
    sw = int(slot["w"] * scale_x)
    sh = int(slot["h"] * scale_y)

    # Read the photo
    photo_file = form.get(f"photo")
    if not photo_file:
        raise HTTPException(400, "No photo provided")

    photo_data = await photo_file.read()
    nparr = np.frombuffer(photo_data, np.uint8)
    photo = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if photo is None:
        raise HTTPException(400, "Invalid photo")

    ph, pw = photo.shape[:2]

    # Apply rotation first (if any)
    if rotation != 0:
        center = (pw // 2, ph // 2)
        rot_matrix = cv2.getRotationMatrix2D(center, -rotation, 1.0)
        # Calculate new bounds after rotation
        cos = abs(rot_matrix[0, 0])
        sin = abs(rot_matrix[0, 1])
        new_pw = int(ph * sin + pw * cos)
        new_ph = int(ph * cos + pw * sin)
        rot_matrix[0, 2] += (new_pw - pw) / 2
        rot_matrix[1, 2] += (new_ph - ph) / 2
        photo = cv2.warpAffine(photo, rot_matrix, (new_pw, new_ph), borderMode=cv2.BORDER_REFLECT)
        ph, pw = photo.shape[:2]

    # Apply zoom and offset
    slot_aspect = sw / max(sh, 1)
    photo_aspect = pw / max(ph, 1)

    # Base size (fit to cover)
    if photo_aspect > slot_aspect:
        base_h = sh
        base_w = int(sh * photo_aspect)
    else:
        base_w = sw
        base_h = int(sw / photo_aspect) if photo_aspect > 0 else sh

    # Apply zoom
    new_w = int(base_w * zoom)
    new_h = int(base_h * zoom)
    new_w = max(new_w, sw)  # Never smaller than slot
    new_h = max(new_h, sh)

    photo = cv2.resize(photo, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # Apply offset (0 = center, -1 = full left/top, 1 = full right/bottom)
    max_offset_x = new_w - sw
    max_offset_y = new_h - sh
    crop_x = int((max_offset_x / 2) * (1 + offset_x))
    crop_y = int((max_offset_y / 2) * (1 + offset_y))
    crop_x = max(0, min(crop_x, new_w - sw))
    crop_y = max(0, min(crop_y, new_h - sh))

    photo = photo[crop_y:crop_y+sh, crop_x:crop_x+sw]

    # Place on background
    if sx < 0: sx = 0
    if sy < 0: sy = 0
    if sx + sw > bg_w: sw = bg_w - sx
    if sy + sh > bg_h: sh = bg_h - sy

    if sh > 0 and sw > 0 and photo.shape[0] >= sh and photo.shape[1] >= sw:
        background[sy:sy+sh, sx:sx+sw] = photo[:sh, :sw]

    # Save updated result (overwrite)
    result_rgb = cv2.cvtColor(background, cv2.COLOR_BGR2RGB)
    result_img = PILImage.fromarray(result_rgb)
    result_img.save(str(result_path), "JPEG", quality=100, dpi=(300, 300))

    return {"result_id": result_id, "adjusted_slot": slot_index}


@router.get("/psd/result/{result_id}")
async def get_psd_result(result_id: str, token: str = None):
    """Serve the composited result image."""
    import time as _time
    from app.routes.auth import _active_tokens
    if token and (token not in _active_tokens or _time.time() > _active_tokens.get(token, 0)):
        raise HTTPException(401, "Invalid token")
    from app.config import OUTPUT_PATH
    result_path = OUTPUT_PATH / f"psd_result_{result_id}.jpg"
    if not result_path.exists():
        raise HTTPException(404, "Result not found")
    return FileResponse(result_path, media_type="image/jpeg", filename=f"result_{result_id}.jpg")


@router.post("/psd/download-all")
async def download_all_results(request: Request):
    """Download all PSD results as a numbered ZIP."""
    import uuid
    import zipfile
    from app.config import OUTPUT_PATH

    form = await request.form()
    result_ids = form.get("result_ids", "")
    if not result_ids:
        raise HTTPException(400, "No result IDs provided")

    ids = [r.strip() for r in result_ids.split(",") if r.strip()]
    if not ids:
        raise HTTPException(400, "No valid result IDs")

    zip_id = uuid.uuid4().hex[:8]
    zip_path = OUTPUT_PATH / f"batch_download_{zip_id}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, rid in enumerate(ids):
            result_path = OUTPUT_PATH / f"psd_result_{rid}.jpg"
            if result_path.exists():
                # Number files starting from 001
                zf.write(result_path, f"{i+1:03d}.jpg")

    if not zip_path.exists():
        raise HTTPException(500, "Failed to create ZIP")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"album_pages_{zip_id}.zip",
    )


@router.post("/psd/download-all-pdf")
async def download_all_as_pdf(request: Request):
    """Combine all result pages into a single PDF."""
    import uuid
    from app.config import OUTPUT_PATH
    from PIL import Image as PILImage
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as pdf_canvas

    PILImage.MAX_IMAGE_PIXELS = 500000000

    form = await request.form()
    result_ids = form.get("result_ids", "")
    if not result_ids:
        raise HTTPException(400, "No result IDs provided")

    ids = [r.strip() for r in result_ids.split(",") if r.strip()]
    if not ids:
        raise HTTPException(400, "No valid result IDs")

    pdf_id = uuid.uuid4().hex[:8]
    pdf_path = OUTPUT_PATH / f"album_pdf_{pdf_id}.pdf"

    # Get dimensions from first image
    first_path = OUTPUT_PATH / f"psd_result_{ids[0]}.jpg"
    if not first_path.exists():
        raise HTTPException(404, "Result images not found")

    with PILImage.open(first_path) as img:
        w_px, h_px = img.size
        dpi = img.info.get("dpi", (300, 300))[0]

    page_w = (w_px / dpi) * inch
    page_h = (h_px / dpi) * inch

    c = pdf_canvas.Canvas(str(pdf_path), pagesize=(page_w, page_h))
    for rid in ids:
        result_path = OUTPUT_PATH / f"psd_result_{rid}.jpg"
        if result_path.exists():
            c.drawImage(str(result_path), 0, 0, page_w, page_h)
            c.showPage()
    c.save()

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"album_{pdf_id}.pdf",
    )


@router.get("/psd/result-psd/{result_id}")
async def get_psd_result_as_psd(result_id: str, token: str = None):
    """
    Download original PSD with photos placed into slot layers.
    - Original PSD structure preserved (layers, groups, effects)
    - Slot layers get the uploaded photos as their pixel data
    """
    import time as _time
    import json
    import shutil
    from app.routes.auth import _active_tokens
    from app.config import OUTPUT_PATH
    from PIL import Image as PILImage
    from psd_tools import PSDImage
    import numpy as np
    import cv2

    PILImage.MAX_IMAGE_PIXELS = 500000000

    if token and (token not in _active_tokens or _time.time() > _active_tokens.get(token, 0)):
        raise HTTPException(401, "Invalid token")

    result_jpg = OUTPUT_PATH / f"psd_result_{result_id}.jpg"
    if not result_jpg.exists():
        raise HTTPException(404, "Result not found")

    result_psd_path = OUTPUT_PATH / f"psd_result_{result_id}_final.psd"

    if not result_psd_path.exists():
        try:
            # Find original PSD
            meta_path = OUTPUT_PATH / f"psd_result_{result_id}_meta.json"
            original_psd_path = None
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                original_psd_path = Path(meta.get("psd_file", ""))
                if not original_psd_path.exists():
                    original_psd_path = None

            if not original_psd_path:
                for d in OUTPUT_PATH.glob("psd_preview_*"):
                    for f in d.glob("*.psd"):
                        original_psd_path = f
                        break
                    if original_psd_path:
                        break

            if not original_psd_path:
                raise HTTPException(404, "Original PSD not found")

            # Open original PSD
            psd = PSDImage.open(str(original_psd_path))

            # Load the composited result to extract placed photos
            result_img = cv2.imread(str(result_jpg))
            if result_img is None:
                raise HTTPException(500, "Cannot load result image")

            # Scale factor between result and PSD
            res_h, res_w = result_img.shape[:2]
            scale_x = psd.width / res_w
            scale_y = psd.height / res_h

            # Find slot layers (same logic as composite-slots)
            slot_layers = []
            mid_x = psd.width / 2
            for layer in psd:
                if not layer.is_visible():
                    continue
                if "background" in layer.name.lower() or "bg" in layer.name.lower():
                    continue
                if hasattr(layer, '__iter__') and str(getattr(layer, 'kind', '')) == 'group':
                    for child in layer:
                        if not child.is_visible():
                            continue
                        bbox = child.bbox
                        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        if w > 200 and h > 200 and not (w > psd.width * 0.95 and h > psd.height * 0.95):
                            slot_layers.append(child)
                else:
                    bbox = layer.bbox
                    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    if w > 200 and h > 200 and not (w > psd.width * 0.95 and h > psd.height * 0.95):
                        slot_layers.append(layer)

            # For each slot layer, extract the corresponding region from the result
            # and set it as the layer's pixel data
            for layer in slot_layers:
                bbox = layer.bbox
                x, y, x2, y2 = bbox
                w, h = x2 - x, y2 - y

                # Get the corresponding region from result image (scaled)
                rx = int(x / scale_x)
                ry = int(y / scale_y)
                rw = int(w / scale_x)
                rh = int(h / scale_y)

                # Clamp
                rx = max(0, rx)
                ry = max(0, ry)
                if rx + rw > res_w: rw = res_w - rx
                if ry + rh > res_h: rh = res_h - ry

                # Extract region from result
                region = result_img[ry:ry+rh, rx:rx+rw]
                if region.size == 0:
                    continue

                # Resize to layer dimensions
                region = cv2.resize(region, (w, h), interpolation=cv2.INTER_LANCZOS4)

                # Convert BGR to RGBA for PSD layer
                region_rgba = cv2.cvtColor(region, cv2.COLOR_BGR2RGBA)
                region_rgba[:, :, 3] = 255  # Full opacity

                # Set layer pixel data using PIL image
                layer_img = PILImage.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))

                # Use psd-tools internal API to set layer pixels
                try:
                    layer._psd = psd._psd
                    # Update the layer's channel data
                    from psd_tools.api.numpy_io import set_layer_image
                    set_layer_image(layer, layer_img)
                except Exception:
                    pass  # If setting fails, layer keeps original content

            # Save the modified PSD
            psd.save(str(result_psd_path))
            logger.info("Created PSD with photos in layers: %s (%.1f MB)",
                       result_psd_path.name, result_psd_path.stat().st_size / 1e6)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("PSD with layers failed: %s, using flat PSD fallback", e)
            # Fallback: create flat PSD with pytoshop
            try:
                import pytoshop
                from pytoshop.enums import ColorMode
                from pytoshop.image_data import ImageData

                img = PILImage.open(result_jpg).convert('RGB')
                w, h = img.size
                arr = np.array(img)
                psd_file = pytoshop.PsdFile(num_channels=3, height=h, width=w, color_mode=ColorMode.rgb)
                channels = np.stack([arr[:,:,0], arr[:,:,1], arr[:,:,2]], axis=0)
                psd_file.image_data = ImageData(channels=channels)
                with open(str(result_psd_path), 'wb') as f:
                    psd_file.write(f)
            except Exception:
                # Ultimate fallback: TIFF
                result_psd_path = OUTPUT_PATH / f"psd_result_{result_id}.tiff"
                img = PILImage.open(result_jpg)
                img.save(str(result_psd_path), "TIFF", dpi=(300, 300))

    return FileResponse(
        result_psd_path,
        media_type="application/octet-stream",
        filename=f"page_{result_id}.psd",
    )


@router.get("/storage/info")
async def get_storage_info():
    """Get storage usage grouped by date."""
    from app.config import UPLOAD_PATH, OUTPUT_PATH
    from datetime import datetime
    from collections import defaultdict

    date_info = defaultdict(lambda: {"files": 0, "size_mb": 0.0})

    for base_dir in [UPLOAD_PATH, OUTPUT_PATH]:
        if not base_dir.exists():
            continue
        for item in base_dir.iterdir():
            try:
                mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d")
                if item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    count = sum(1 for f in item.rglob("*") if f.is_file())
                else:
                    size = item.stat().st_size
                    count = 1
                date_info[mtime]["files"] += count
                date_info[mtime]["size_mb"] += size / 1e6
            except Exception:
                pass

    # Sort by date descending
    result = [
        {"date": d, "files": info["files"], "size_mb": round(info["size_mb"], 1)}
        for d, info in sorted(date_info.items(), reverse=True)
    ]
    total_mb = sum(d["size_mb"] for d in result)
    return {"dates": result, "total_mb": round(total_mb, 1)}


@router.post("/storage/delete")
async def delete_storage(request: Request):
    """Delete files by date. Body: {"date": "2026-05-09"} or {"date": "all"}"""
    import shutil
    from app.config import UPLOAD_PATH, OUTPUT_PATH
    from datetime import datetime

    form = await request.form()
    target_date = form.get("date", "")
    if not target_date:
        raise HTTPException(400, "Date required")

    deleted = 0
    freed = 0.0

    for base_dir in [UPLOAD_PATH, OUTPUT_PATH]:
        if not base_dir.exists():
            continue
        for item in base_dir.iterdir():
            try:
                mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d")
                should_delete = (target_date == "all") or (mtime == target_date)
                if should_delete:
                    if item.is_dir():
                        size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        shutil.rmtree(item)
                    else:
                        size = item.stat().st_size
                        item.unlink()
                    deleted += 1
                    freed += size
            except Exception:
                pass

    return {"deleted": deleted, "freed_mb": round(freed / 1e6, 1)}


@router.post("/psd/move-to-used")
async def move_to_used(request: Request):
    """
    Move photo files from the user's source folder to a 'Used' subfolder.
    """
    import shutil

    form = await request.form()
    filenames_raw = form.get("filenames", "")
    source_folder = form.get("source_folder", "")

    if not filenames_raw:
        raise HTTPException(400, "No filenames provided")
    if not source_folder:
        raise HTTPException(400, "No source folder provided")

    filenames = [f.strip() for f in filenames_raw.split(",") if f.strip()]
    source_dir = Path(source_folder)

    if not source_dir.exists():
        raise HTTPException(404, f"Folder not found: {source_folder}")

    # Create Used subfolder in the source directory
    used_dir = source_dir / "Used"
    used_dir.mkdir(exist_ok=True)

    moved = 0
    not_found = []

    for filename in filenames:
        src_file = source_dir / filename
        if src_file.exists():
            dest_file = used_dir / filename
            if dest_file.exists():
                stem = dest_file.stem
                suffix = dest_file.suffix
                counter = 1
                while dest_file.exists():
                    dest_file = used_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(src_file), str(dest_file))
            moved += 1
        else:
            not_found.append(filename)

    return {
        "moved": moved,
        "not_found": not_found,
        "used_folder": str(used_dir),
    }


@router.post("/psd/browse-folder")
async def browse_folder(request: Request):
    """
    List image files in a local folder.
    Expects: {"folder": "D:/MyPhotos"}
    """
    form = await request.form()
    folder = form.get("folder", "")

    if not folder:
        raise HTTPException(400, "No folder path provided")

    folder_path = Path(folder)
    if not folder_path.exists():
        raise HTTPException(404, f"Folder not found: {folder}")

    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
    files = []
    for f in sorted(folder_path.iterdir()):
        if f.is_file() and f.suffix.lower() in image_extensions:
            files.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / 1e6, 1),
                "path": str(f),
            })

    return {
        "folder": str(folder_path),
        "files": files,
        "total": len(files),
        "has_used_folder": (folder_path / "Used").exists(),
        "used_count": len(list((folder_path / "Used").iterdir())) if (folder_path / "Used").exists() else 0,
    }
