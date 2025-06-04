from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import aiofiles
import tempfile
import io
import base64
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class OCRResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    extracted_text: str
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TextEdit(BaseModel):
    text: str
    x: int
    y: int
    font_size: int = 24
    font_color: str = "#000000"

class EditRequest(BaseModel):
    file_id: str
    edits: List[TextEdit]

# Utility functions
def preprocess_image(image):
    """Preprocess image for better OCR results"""
    # Convert PIL to numpy array
    img_array = np.array(image)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # Apply threshold to get a binary image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Noise removal
    kernel = np.ones((1, 1), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPENING, kernel, iterations=1)
    
    # Convert back to PIL Image
    return Image.fromarray(opening)

async def extract_text_from_image(image: Image.Image) -> tuple[str, float]:
    """Extract text from image using Tesseract OCR"""
    try:
        # Preprocess image for better OCR
        processed_image = preprocess_image(image)
        
        # Configure Tesseract
        custom_config = r'--oem 3 --psm 6'
        
        # Extract text with confidence
        data = pytesseract.image_to_data(processed_image, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Get text and calculate average confidence
        texts = []
        confidences = []
        
        for i in range(len(data['text'])):
            if int(data['conf'][i]) > 30:  # Filter out low confidence text
                text = data['text'][i].strip()
                if text:
                    texts.append(text)
                    confidences.append(int(data['conf'][i]))
        
        extracted_text = ' '.join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return extracted_text, avg_confidence
    except Exception as e:
        logging.error(f"OCR extraction failed: {str(e)}")
        return "", 0.0

def add_text_to_image(image: Image.Image, edits: List[TextEdit]) -> Image.Image:
    """Add text overlays to image"""
    # Create a copy of the image
    img_with_text = image.copy()
    draw = ImageDraw.Draw(img_with_text)
    
    for edit in edits:
        try:
            # Try to use a better font, fallback to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", edit.font_size)
            except:
                font = ImageFont.load_default()
            
            # Convert hex color to RGB
            color = edit.font_color
            if color.startswith('#'):
                color = color[1:]
            color_rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            
            # Add text to image
            draw.text((edit.x, edit.y), edit.text, font=font, fill=color_rgb)
        except Exception as e:
            logging.error(f"Failed to add text: {str(e)}")
            continue
    
    return img_with_text

# API Routes
@api_router.get("/")
async def root():
    return {"message": "OCR Converter API"}

@api_router.post("/upload-ocr", response_model=OCRResult)
async def upload_and_extract_text(file: UploadFile = File(...)):
    """Upload image and extract text using OCR"""
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    
    try:
        # Read the file
        contents = await file.read()
        
        # Open image with PIL
        image = Image.open(io.BytesIO(contents))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extract text
        extracted_text, confidence = await extract_text_from_image(image)
        
        # Create OCR result
        ocr_result = OCRResult(
            filename=file.filename,
            extracted_text=extracted_text,
            confidence=confidence
        )
        
        # Save to database
        await db.ocr_results.insert_one(ocr_result.dict())
        
        # Save original image for later editing
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
        
        # Store image data
        await db.images.insert_one({
            "id": ocr_result.id,
            "filename": file.filename,
            "image_data": img_base64,
            "timestamp": datetime.utcnow()
        })
        
        return ocr_result
        
    except Exception as e:
        logging.error(f"Upload and OCR failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@api_router.get("/ocr-results", response_model=List[OCRResult])
async def get_ocr_results():
    """Get all OCR results"""
    try:
        results = await db.ocr_results.find().to_list(100)
        return [OCRResult(**result) for result in results]
    except Exception as e:
        logging.error(f"Failed to get OCR results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve OCR results")

@api_router.post("/edit-image")
async def edit_image_with_text(edit_request: EditRequest):
    """Add text edits to an image and return the modified image"""
    
    try:
        # Get original image from database
        image_doc = await db.images.find_one({"id": edit_request.file_id})
        if not image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Decode base64 image
        img_data = base64.b64decode(image_doc["image_data"])
        image = Image.open(io.BytesIO(img_data))
        
        # Add text edits
        edited_image = add_text_to_image(image, edit_request.edits)
        
        # Convert to bytes for response
        img_bytes = io.BytesIO()
        edited_image.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return StreamingResponse(
            io.BytesIO(img_bytes.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=edited_{image_doc['filename']}"}
        )
        
    except Exception as e:
        logging.error(f"Image editing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to edit image: {str(e)}")

@api_router.get("/image/{file_id}")
async def get_image(file_id: str):
    """Get original image by ID"""
    try:
        image_doc = await db.images.find_one({"id": file_id})
        if not image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Decode base64 image
        img_data = base64.b64decode(image_doc["image_data"])
        
        return StreamingResponse(
            io.BytesIO(img_data),
            media_type="image/png"
        )
        
    except Exception as e:
        logging.error(f"Failed to get image: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve image")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()