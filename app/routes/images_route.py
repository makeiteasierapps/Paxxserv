import io
from PIL import Image
from dotenv import load_dotenv
import mimetypes
import os
from fastapi import APIRouter, Header, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import requests
from app.services.LocalStorageService import LocalStorageService
from app.services.MongoDbClient import MongoDbClient
from app.agents.OpenAiClient import OpenAiClient
load_dotenv()

router = APIRouter()

def get_db_and_image_manager(dbName: str = Header(...), uid: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        openai_client = OpenAiClient(db, uid)
        return db, openai_client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@router.post("/images")
async def generate_image(request: Request, db_and_manager: tuple = Depends(get_db_and_image_manager)):
    _, openai_client = db_and_manager
    image_request = await request.json()
    size = image_request.get('size', '1024x1024').lower()
    quality = image_request.get('quality', 'standard').lower()
    style = image_request.get('style', 'natural').lower()
    prompt = image_request.get('prompt')
    image_url = openai_client.generate_image(prompt, size, quality, style)
    return JSONResponse(content=image_url, status_code=200)

@router.get("/images")
async def get_images(uid: str = Header(...)):
    full_images = LocalStorageService.fetch_all_images(uid, 'dalle_images')
    thumbnails = LocalStorageService.fetch_all_images(uid, 'dalle_images/thumbnails')
    result = []
    for full_image in full_images:
        file_name = os.path.basename(full_image['path'])
        base_name, ext = os.path.splitext(file_name)
        thumbnail_name = f"{base_name}_thumb{ext}"
        
        thumbnail = next((t['path'] for t in thumbnails if os.path.basename(t['path']) == thumbnail_name), None)
        result.append({
            "full_image": full_image['path'],
            "thumbnail": thumbnail
        })
    
    return JSONResponse(content=result, status_code=200)

@router.get("/images/{image_path:path}")
async def get_image(image_path: str):
    full_path = os.path.join(LocalStorageService.base_path, image_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    def iterfile():
        with open(full_path, "rb") as image_file:
            yield from image_file

    return StreamingResponse(iterfile(), media_type="image/jpeg")

@router.delete("/images")
async def delete_image(request: Request):
    data = await request.json()
    path = data.get('path')
    LocalStorageService.delete_image(path)
    return JSONResponse(content={'message': 'Image deleted successfully'}, status_code=200)

@router.post("/images/save")
async def save_image(request: Request, uid: str = Header(...)):
    data = await request.json()
    url = data.get('image')
    prompt = data.get('prompt')
    
    # Fetch the image
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail='Failed to fetch image')
    
    # Determine file extension from content-type
    content_type = response.headers.get('content-type')
    ext = mimetypes.guess_extension(content_type) or ''
    
    # Create a file name from the prompt
    safe_prompt = prompt.replace(' ', '_')[:50]  # Limit to 50 characters
    file_name = f"{safe_prompt}{ext}"
    thumbnail_name = f"{safe_prompt}_thumb{ext}"
    
    # Prepare the image data
    image_data = response.content
    image_blob = io.BytesIO(image_data)
    
    # Create thumbnail
    with Image.open(image_blob) as img:
        img.thumbnail((200, 200))  # This maintains aspect ratio
        thumb_blob = io.BytesIO()
        img.save(thumb_blob, format=img.format)
        thumb_blob.seek(0)
    
    # Reset image_blob to the beginning
    image_blob.seek(0)
    
    # Save both images
    full_image_url = await LocalStorageService.upload_file_async(image_blob, uid, 'dalle_images', file_name=file_name)
    print(full_image_url)
    thumb_url = await LocalStorageService.upload_file_async(thumb_blob, uid, 'dalle_images/thumbnails', file_name=thumbnail_name)
    print(thumb_url)

    
    return JSONResponse(content={"full_image": full_image_url, "thumbnail": thumb_url}, status_code=200)
