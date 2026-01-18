from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image
import io
import datetime
import json
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="ESP32-CAM Backend API with Gemini")

# Configure Gemini API using new google-genai package
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️  ERROR: GEMINI_API_KEY not found in environment variables!")
    print("Please create a .env file with: GEMINI_API_KEY=your-api-key-here")

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory
DATA_DIR = Path("captured_images")
DATA_DIR.mkdir(exist_ok=True)
METADATA_FILE = DATA_DIR / "metadata.json"

def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def pil_to_gemini_image(pil_image):
    """Convert PIL Image to bytes for Gemini API"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    return img_byte_arr.read()

def process_image_with_gemini(image):
    """
    Process image using Google Gemini Vision API
    Returns basic info suitable for OLED display
    """
    try:
        # Convert PIL image to bytes
        image_bytes = pil_to_gemini_image(image)
        
        # Create prompt for basic info response
        prompt = """Provide ONLY basic information about this image in under 60 characters:
        - What is the main object/subject?
        - Brief status or description
        
        Format: "Subject: [name], [brief description]"
        Example: "Subject: Person, standing indoors"
        Be extremely concise and factual."""
        
        # Generate response using Gemini with new API
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
                    ]
                )
            ]
        )
        
        # Extract text from response
        ai_response = response.text.strip()
        
        # Truncate if too long for OLED (max ~100 chars for good display)
        if len(ai_response) > 100:
            ai_response = ai_response[:97] + "..."
        
        return ai_response
        
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return f"Error: {str(e)[:50]}"

def process_image_detailed(image):
    """
    Get detailed analysis for dashboard display
    """
    try:
        # Convert PIL image to bytes
        image_bytes = pil_to_gemini_image(image)
        
        prompt = """Analyze this image in detail and provide:
        1. Main objects or subjects identified
        2. Scene description and context
        3. Any notable activities or concerns
        4. Image quality assessment
        5. Suggested actions if any
        
        Provide a comprehensive but concise analysis."""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type='image/jpeg'
                        )
                    ]
                )
            ]
        )
        
        return response.text.strip()
        
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return f"Detailed analysis error: {str(e)}"

@app.get("/")
async def root():
    return {
        "message": "ESP32-CAM Backend API with Gemini AI",
        "status": "running",
        "ai_model": "Google Gemini 1.5 Flash",
        "api_configured": GEMINI_API_KEY is not None,
        "endpoints": {
            "/upload": "POST - Upload image from ESP32",
            "/images": "GET - List all images",
            "/latest": "GET - Get latest image info",
            "/health": "GET - Check Gemini API status"
        }
    }

@app.get("/health")
async def health_check():
    """Check if Gemini API is configured properly"""
    if not GEMINI_API_KEY:
        return {
            "status": "error",
            "message": "Gemini API key not configured. Check .env file."
        }
    
    try:
        # Test API with simple request
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents='Say "OK" if you can read this.'
        )
        
        return {
            "status": "healthy",
            "gemini_configured": True,
            "test_response": response.text
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"API test failed: {str(e)}"
        }

@app.post("/upload")
async def upload_image(request: Request):
    """
    Endpoint for ESP32-CAM to upload images
    Expects raw image bytes in request body
    """
    try:
        # Read raw image bytes
        img_bytes = await request.body()
        
        if not img_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": "No image data received"}
            )
        
        # Open image
        image = Image.open(io.BytesIO(img_bytes))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Process with Gemini - Get short response for OLED
        print("Processing image with Gemini AI...")
        ai_response_short = process_image_with_gemini(image)
        
        # Get detailed response for dashboard
        ai_response_detailed = process_image_detailed(image)
        
        # Save image
        timestamp = datetime.datetime.now()
        filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = DATA_DIR / filename
        image.save(filepath, "JPEG")
        
        # Update metadata
        metadata = load_metadata()
        new_entry = {
            "filename": filename,
            "timestamp": timestamp.isoformat(),
            "ai_response_short": ai_response_short,
            "ai_response_detailed": ai_response_detailed,
            "size": f"{image.size[0]}x{image.size[1]}"
        }
        metadata.append(new_entry)
        save_metadata(metadata)
        
        print(f"[{timestamp}] Image saved: {filename}")
        print(f"Gemini Response (OLED): {ai_response_short}")
        print(f"Gemini Response (Detailed): {ai_response_detailed[:100]}...")
        
        # Return short AI response to ESP32 (will be displayed on OLED)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": ai_response_short,
                "filename": filename
            }
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing upload: {error_msg}")
        
        # Return user-friendly error for OLED
        if "API_KEY" in error_msg or "api_key" in error_msg:
            oled_msg = "API key error"
        elif "quota" in error_msg.lower():
            oled_msg = "API quota exceeded"
        else:
            oled_msg = "Processing error"
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": oled_msg
            }
        )

@app.get("/images")
async def list_images():
    """Get list of all captured images"""
    metadata = load_metadata()
    return {
        "total": len(metadata),
        "images": metadata
    }

@app.get("/latest")
async def get_latest():
    """Get latest captured image info"""
    metadata = load_metadata()
    if metadata:
        return metadata[-1]
    return {"message": "No images yet"}

@app.delete("/clear")
async def clear_all():
    """Clear all images and metadata"""
    try:
        # Delete all images
        for img_file in DATA_DIR.glob("*.jpg"):
            img_file.unlink()
        
        # Clear metadata
        save_metadata([])
        
        return {"status": "success", "message": "All data cleared"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/test-gemini")
async def test_gemini():
    """Test endpoint to verify Gemini integration"""
    try:
        # Create a simple test image
        test_image = Image.new('RGB', (100, 100), color='blue')
        test_bytes = pil_to_gemini_image(test_image)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text="Describe this image in one sentence."),
                        types.Part.from_bytes(
                            data=test_bytes,
                            mime_type='image/jpeg'
                        )
                    ]
                )
            ]
        )
        
        return {
            "status": "success",
            "gemini_response": response.text,
            "message": "Gemini API is working correctly"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Gemini API test failed"
        }

if __name__ == "__main__":
    print("=" * 60)
    print("ESP32-CAM Backend Server with Gemini AI")
    print("=" * 60)
    
    if not GEMINI_API_KEY:
        print("\n⚠️  WARNING: Gemini API key not configured!")
        print("Please create a .env file with:")
        print("GEMINI_API_KEY=your-api-key-here\n")
    else:
        print("✓ Gemini API key loaded from .env file")
    
    print(f"\nServer starting on: http://0.0.0.0:8000")
    print(f"Upload endpoint: http://YOUR_IP:8000/upload")
    print(f"API Docs: http://YOUR_IP:8000/docs")
    print(f"Test Gemini: http://YOUR_IP:8000/test-gemini")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )