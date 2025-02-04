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
        insight_service = InsightService(db, uid, llm_client)
        analyze_user = AnalyzeUser(db, uid)
        return {"db": db, "analyze_user": analyze_user, "mongo_client": mongo_client, "insight_service": insight_service}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@router.post("/insight/generate_questions")
async def generate_questions(request: Request, services: dict = Depends(get_services)):
    content = await request.json()
    await services["db"]['users'].update_one({'_id': services["profile_service"].uid}, {'$set': {'userintro': content['userInput']}})
    
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

@router.get("/insight/questions")
async def get_questions(services: dict = Depends(get_services)):
    questions = await services["insight_service"].load_questions()
    return JSONResponse(content=questions)

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