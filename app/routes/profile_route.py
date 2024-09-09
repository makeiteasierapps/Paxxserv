from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from app.services.ProfileService import ProfileService
from app.services.UserService import UserService
from app.services.MongoDbClient import MongoDbClient
from app.agents.QuestionGenerator import QuestionGenerator
from app.agents.AnalyzeUser import AnalyzeUser
import json
import traceback

load_dotenv()

router = APIRouter(prefix="/api")

def get_services(dbName: str = Header(...), uid: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        profile_service = ProfileService(db, uid)
        user_service = UserService(db)
        analyze_user = AnalyzeUser(db, uid)
        return {"db": db, "profile_service": profile_service, "user_service": user_service, "analyze_user": analyze_user, "mongo_client": mongo_client}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@router.get("/profile")
async def get_profile(services: dict = Depends(get_services)):
    user_profile = services["profile_service"].get_profile(services["profile_service"].uid)
    return JSONResponse(content=user_profile)

@router.post("/profile/generate_questions")
async def generate_questions(request: Request, services: dict = Depends(get_services)):
    content = await request.json()
    services["db"]['users'].update_one({'_id': services["profile_service"].uid}, {'$set': {'userintro': content['userInput']}})
    
    async def generate():
        try:
            question_generator = QuestionGenerator(services["db"], services["profile_service"].uid)
            for result in question_generator.generate_questions(content['userInput']):
                yield json.dumps(result) + '\n'
        except Exception as e:
            error_msg = f"Error in generate_questions: {str(e)}\n{traceback.format_exc()}"
            yield json.dumps({"error": error_msg}) + '\n'
        finally:
            services["mongo_client"].close()
            yield ''  # Ensure the stream is properly closed

    return StreamingResponse(generate(), media_type='application/json')

@router.get("/profile/questions")
async def get_questions(services: dict = Depends(get_services)):
    questions = services["profile_service"].load_questions(services["profile_service"].uid)
    return JSONResponse(content=questions)

@router.post("/profile/answers")
async def update_answers(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    question_id = data['questionId']
    answer = data['answer']
    services["profile_service"].update_profile_answer(question_id, answer)
    return JSONResponse(content={'response': 'Profile questions/answers updated successfully'})

@router.post("/profile/user")
async def update_user_profile(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    services["profile_service"].update_user_profile(services["profile_service"].uid, data)
    return JSONResponse(content={'response': 'User profile updated successfully'})

@router.post("/profile/analyze")
async def analyze_profile(services: dict = Depends(get_services)):
    answered_questions = services["profile_service"].load_questions(services["profile_service"].uid, fetch_answered=True)
    response = services["analyze_user"].analyze_cateogry(answered_questions)
    return JSONResponse(content=response)

@router.post("/profile/update_avatar")
async def update_avatar(file: UploadFile = File(...), services: dict = Depends(get_services)):
    try:
        uid = services["profile_service"].uid
        print(uid)
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