from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from app.services.InsightService import InsightService
from app.agents.AnalyzeUser import AnalyzeUser

load_dotenv()

router = APIRouter()

def get_services(request: Request, uid: str = Header(...)):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        sio = request.app.state.sio
        insight_service = InsightService(db, sio, uid)
        analyze_user = AnalyzeUser(db, uid)
        return {"db": db, "analyze_user": analyze_user, "mongo_client": mongo_client, "insight_service": insight_service, "uid": uid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@router.get("/insight")
async def get_questions(services: dict = Depends(get_services)):
    insight_data = await services["insight_service"].get_user_insight()
    if insight_data:
        return JSONResponse(content=insight_data.model_dump())
    return JSONResponse(content={'response': 'No insight data found'})
    
@router.post("/insight/update_answer")
async def update_answers(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    await services["insight_service"].update_profile_answer(data)
    return JSONResponse(content={'response': 'Profile questions/answers updated successfully'})

@router.post("/insight/analyze")
async def analyze_profile(services: dict = Depends(get_services)):
    answered_questions = await services["insight_service"].load_questions(fetch_answered=True)
    response = await services["analyze_user"].analyze_cateogry(answered_questions)
    return JSONResponse(content=response)