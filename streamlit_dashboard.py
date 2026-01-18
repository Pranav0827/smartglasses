import streamlit as st
import io
from PIL import Image
import datetime
import json
import os
from pathlib import Path
import base64

# Page config
st.set_page_config(
    page_title="ESP32-CAM Dashboard",
    page_icon="📷",
    layout="wide"
)

# Initialize data directory
DATA_DIR = Path("captured_images")
DATA_DIR.mkdir(exist_ok=True)
METADATA_FILE = DATA_DIR / "metadata.json"

# Load or initialize metadata
def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

# Process image using Gemini API
def process_image_with_ai(image):
    """
    This is a placeholder for testing the dashboard
    The actual Gemini processing happens in the FastAPI backend
    """
    import random
    short_responses = [
        "Person detected",
        "Motion in frame",
        "Clear view",
        "Low light detected"
    ]
    detailed_responses = [
        "Image shows a person in the frame with good lighting conditions. No unusual activity detected.",
        "Motion detected in the central area. Scene appears to be indoors with moderate lighting.",
        "Clear view of the monitored area. No objects of concern identified.",
        "Low light conditions detected. Consider improving illumination for better image quality."
    ]
    
    idx = random.randint(0, len(short_responses) - 1)
    return short_responses[idx], detailed_responses[idx]

# API endpoint to receive images from ESP32
def handle_upload():
    """Handle image upload from ESP32"""
    if st.session_state.get('uploaded_image'):
        img_bytes = st.session_state.uploaded_image
        
        # Process image
        image = Image.open(io.BytesIO(img_bytes))
        
        # Generate AI response
        ai_response = process_image_with_ai(image)
        
        # Save image
        timestamp = datetime.datetime.now()
        filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = DATA_DIR / filename
        image.save(filepath)
        
        # Update metadata
        metadata = load_metadata()
        metadata.append({
            "filename": filename,
            "timestamp": timestamp.isoformat(),
            "ai_response": ai_response
        })
        save_metadata(metadata)
        
        return ai_response
    return None

# Main dashboard
def main():
    st.title("📷 ESP32-CAM Dashboard")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Controls")
        
        # Manual upload for testing
        uploaded_file = st.file_uploader(
            "Upload Image (Testing)", 
            type=['jpg', 'jpeg', 'png']
        )
        
        if uploaded_file:
            img_bytes = uploaded_file.read()
            image = Image.open(io.BytesIO(img_bytes))
            
            # Process and save
            ai_response_short, ai_response_detailed = process_image_with_ai(image)
            
            timestamp = datetime.datetime.now()
            filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            filepath = DATA_DIR / filename
            image.save(filepath)
            
            metadata = load_metadata()
            metadata.append({
                "filename": filename,
                "timestamp": timestamp.isoformat(),
                "ai_response_short": ai_response_short,
                "ai_response_detailed": ai_response_detailed
            })
            save_metadata(metadata)
            
            st.success("Image uploaded!")
            st.rerun()
        
        st.markdown("---")
        
        # Settings
        st.subheader("Display Settings")
        show_count = st.slider("Images to display", 5, 50, 10)
        
        if st.button("🗑️ Clear All Data"):
            if st.checkbox("Confirm deletion"):
                for f in DATA_DIR.glob("*.jpg"):
                    f.unlink()
                METADATA_FILE.unlink(missing_ok=True)
                st.success("All data cleared!")
                st.rerun()
    
    # Main content
    col1, col2, col3 = st.columns(3)
    
    metadata = load_metadata()
    
    with col1:
        st.metric("Total Images", len(metadata))
    
    with col2:
        if metadata:
            latest = datetime.datetime.fromisoformat(metadata[-1]['timestamp'])
            st.metric("Last Capture", latest.strftime("%H:%M:%S"))
        else:
            st.metric("Last Capture", "N/A")
    
    with col3:
        if metadata:
            today = sum(1 for m in metadata 
                       if datetime.datetime.fromisoformat(m['timestamp']).date() 
                       == datetime.date.today())
            st.metric("Today's Captures", today)
        else:
            st.metric("Today's Captures", 0)
    
    st.markdown("---")
    
    # Display images
    st.header("📸 Captured Images")
    
    if not metadata:
        st.info("No images captured yet. Waiting for ESP32-CAM...")
    else:
        # Reverse to show latest first
        for item in reversed(metadata[-show_count:]):
            with st.container():
                col_img, col_info = st.columns([1, 2])
                
                with col_img:
                    img_path = DATA_DIR / item['filename']
                    if img_path.exists():
                        st.image(str(img_path), use_container_width=True)
                
                with col_info:
                    timestamp = datetime.datetime.fromisoformat(item['timestamp'])
                    st.subheader(f"🕒 {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Show short response (OLED version)
                    st.markdown("**OLED Display:**")
                    st.code(item.get('ai_response_short', item.get('ai_response', 'N/A')))
                    
                    # Show detailed analysis
                    st.markdown("**Gemini AI Analysis:**")
                    st.info(item.get('ai_response_detailed', item.get('ai_response', 'N/A')))
                    
                    # Download button
                    if img_path.exists():
                        with open(img_path, 'rb') as f:
                            st.download_button(
                                "⬇️ Download",
                                f.read(),
                                file_name=item['filename'],
                                mime="image/jpeg"
                            )
                
                st.markdown("---")

# REST API endpoint simulation
def api_endpoint():
    """
    For actual deployment, use a proper REST API framework like FastAPI
    This is a simplified version for demonstration
    """
    st.header("API Endpoint")
    st.code("""
# ESP32 should POST to: http://YOUR_SERVER_IP:8501/upload
# Content-Type: application/octet-stream
# Body: raw image bytes
    """)

if __name__ == "__main__":
    # Check for API mode
    if st.query_params.get("mode") == "api":
        api_endpoint()
    else:
        main()