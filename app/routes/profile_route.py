from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from app.services.ProfileService import ProfileService
from app.services.UserService import UserService

load_dotenv()

router = APIRouter()

def get_services(request: Request, uid: str = Header(...)):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        profile_service = ProfileService(db, uid)
        user_service = UserService(db)
        return {"db": db, "profile_service": profile_service, "user_service": user_service, "mongo_client": mongo_client}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@router.get("/profile")
async def get_profile(services: dict = Depends(get_services)):
    user_profile = await services["profile_service"].get_profile(services["profile_service"].uid)
    return JSONResponse(content=user_profile)

@router.post("/profile/user")
async def update_user_profile(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    await services["profile_service"].update_user_profile(services["profile_service"].uid, data)
    return JSONResponse(content={'response': 'User profile updated successfully'})


@router.post("/profile/update_avatar")
async def update_avatar(file: UploadFile = File(...), services: dict = Depends(get_services)):
    try:
        uid = services["profile_service"].uid
        if uid is None:
            raise ValueError("UID is None")
        file_path = await services["user_service"].update_user_avatar(uid, file)
        return {"path": file_path}
    except Exception as e:
        print(f"Error in update_avatar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Avatar update failed: {str(e)}")

# Additional error handling - catch all
@router.api_route("/profile/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(path: str):
    raise HTTPException(status_code=404, detail="Not Found")