import os
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
import logging
import base64
import json
import tempfile
from io import BytesIO
from typing import Optional, List, Any, Dict

import numpy as np
import paddle
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from pydantic import BaseModel, Field
from PIL import Image
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_api")

app = FastAPI(title="PaddleOCR-VL Compatible API")

# Initialize OCR
ocr = PaddleOCR(lang="ar", use_textline_orientation=True)

class OCRRequest(BaseModel):
    file: Optional[str] = None
    file_base64: Optional[str] = None
    useLayoutDetection: bool = True
    fileType: str = "image"
    useDocUnwarping: bool = False
    useDocOrientationClassify: bool = False
    useChartRecognition: bool = False
    promptLabel: Optional[str] = None

def to_python(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj

def run_ocr_full(path: str):
    """
    Returns both simple text (for markdown) and boxes (for overlay).
    """
    result = ocr.predict(path)
    if not result:
        return "", []
    
    page = result[0]
    texts = page.get("rec_texts", [])
    scores = page.get("rec_scores", [])
    boxes = page.get("rec_polys") or page.get("rec_boxes") or []
    
    # 1. Text for Markdown
    md_text = "\n".join(texts)
    
    # 2. Items for Overlay
    items = []
    for i in range(len(texts)):
        items.append({
            "text": texts[i],
            "score": to_python(scores[i]) if i < len(scores) else 0.0,
            "box": [to_python(pt) for pt in boxes[i]] if i < len(boxes) else []
        })
        
    return md_text, items

@app.post("/ocr")
async def ocr_endpoint(payload: OCRRequest):
    logger.info(f"Received Request")
    
    b64_str = payload.file or payload.file_base64
    if not b64_str:
        raise HTTPException(400, "No file provided")
    
    try:
        content = base64.b64decode(b64_str)
    except:
        raise HTTPException(400, "Invalid Base64")
        
    markdown_result = ""
    box_items = []
    
    # Process Image/PDF
    # (Simplified for image-only to keep this short, PDF logic same as before)
    # IS_PDF logic:
    is_pdf = (payload.fileType == 'pdf') or (content[:4] == b"%PDF")
    
    suffix = ".pdf" if is_pdf else ".png"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        if is_pdf:
             try:
                images = convert_from_bytes(content, dpi=200, first_page=1, last_page=1)
                if images:
                    # Save as PNG for OCR
                    tmp_png = tmp.name + ".png"
                    images[0].save(tmp_png)
                    markdown_result, box_items = run_ocr_full(tmp_png)
                    if os.path.exists(tmp_png): os.unlink(tmp_png)
             except Exception as e:
                logger.error(f"PDF Error: {e}")
        else:
            tmp.write(content)
            tmp.flush()
            markdown_result, box_items = run_ocr_full(tmp.name)
        
        # Cleanup
        try:
            tmp.close()
            os.unlink(tmp.name)
        except: pass

    # Construct Hybrid Response
    # 1. PaddleOCR-VL format (nested result)
    # 2. Legacy 'pages' format (top-level) for Odoo Overlay
    
    response = {
        "errorCode": 0,
        "result": {
            "layoutParsingResults": [
                {
                    "markdown": { "text": markdown_result, "images": {} },
                    "outputImages": {}
                }
            ]
        },
        # Hybrid Add-on:
        "pages": [
            {
                "items": box_items
            }
        ]
    }
    
    return response