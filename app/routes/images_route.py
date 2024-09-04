import io
from dotenv import load_dotenv
from fastapi import APIRouter, Header, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
import requests
from app.services.LocalStorageService import LocalStorageService
from app.agents.ImageManager import ImageManager
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

router = APIRouter()

def get_db_and_image_manager(dbName: str = Header(...), uid: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        image_manager = ImageManager(db, uid)
        return db, image_manager
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@router.post("/images")
async def generate_image(request: Request, db_and_manager: tuple = Depends(get_db_and_image_manager)):
    _, image_manager = db_and_manager
    image_request = await request.json()
    image_url = image_manager.generate_image(image_request)
    return JSONResponse(content=image_url, status_code=200)

@router.get("/images")
async def get_images(uid: str = Header(...)):
    images_list = LocalStorageService.fetch_all_images(uid, 'dalle_images')
    return JSONResponse(content=images_list, status_code=200)

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
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail='Failed to fetch image')
    image_data = response.content
    image_blob = io.BytesIO(image_data)
    image_url = LocalStorageService.upload_file(image_blob, uid, 'dalle_images')
    return JSONResponse(content=image_url, status_code=200)
