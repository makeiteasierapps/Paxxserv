from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from app.services.InsightService import InsightService
from app.agents.QuestionGenerator import QuestionGenerator
from app.agents.AnalyzeUser import AnalyzeUser
from app.agents.OpenAiClient import OpenAiClient
import json
import traceback

load_dotenv()

router = APIRouter()

def get_services(request: Request, uid: str = Header(...)):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        llm_client = OpenAiClient(db, uid)
        question_generator = QuestionGenerator(llm_client)
        insight_service = InsightService(db, uid, llm_client, question_generator)
        analyze_user = AnalyzeUser(db, uid)
        return {"db": db, "analyze_user": analyze_user, "mongo_client": mongo_client, "insight_service": insight_service, "uid": uid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@router.post("/insight/generate_questions")
async def generate_questions(request: Request, services: dict = Depends(get_services)):
    user_intro = await request.json()
    user_profile, question_set = await services["insight_service"].initial_user_onboarding(user_intro)
    mongo_client = services["mongo_client"]
    insight_model = {
        "uid": services["uid"],
        "user_profile": user_profile,
        "question_set": question_set.model_dump()
    }
    mongo_client.db.insight.insert_one(insight_model)
    return {'user_profile': user_profile, 'question_set': question_set.model_dump()}

@router.get("/insight")
async def get_questions(services: dict = Depends(get_services)):
    return await services["insight_service"].get_user_insight()
    
@router.post("/insight/answers")
async def update_answers(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    question_id = data['questionId']
    answer = data['answer']
    await services["insight_service"].update_profile_answer(question_id, answer)
    return JSONResponse(content={'response': 'Profile questions/answers updated successfully'})

@router.post("/insight/analyze")
async def analyze_profile(services: dict = Depends(get_services)):
    answered_questions = await services["insight_service"].load_questions(fetch_answered=True)
    response = await services["analyze_user"].analyze_cateogry(answered_questions)
    return JSONResponse(content=response)