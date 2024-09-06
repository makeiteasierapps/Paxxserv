import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from typing import Optional
from dotenv import load_dotenv
from app.utils.custom_json_encoder import CustomJSONEncoder
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService

load_dotenv()

router = APIRouter()

def get_services(dbName: str = Header(...), uid: str = Header(...)):
    mongo_client = MongoDbClient(dbName)
    db = mongo_client.connect()
    kb_services = KnowledgeBaseService(db, uid)
    return {"mongo_client": mongo_client, "db": db, "kb_services": kb_services, "uid": uid}

@router.get("/kb")
async def get_kb_list(services: dict = Depends(get_services)):
    kb_list = services["kb_services"].get_kb_list(services["uid"])
    json_kb_list = jsonable_encoder(kb_list)
    json_str = json.dumps(json_kb_list, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))

@router.post("/kb")
async def create_kb(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    name = data.get('name')
    objective = data.get('objective')
    new_kb_details = services["kb_services"].create_new_kb(services["uid"], name, objective)
    json_kb_details = jsonable_encoder(new_kb_details)
    json_str = json.dumps(json_kb_details, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))

@router.delete("/kb")
async def delete_kb(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    kb_id = data.get('kbId')
    if not kb_id:
        raise HTTPException(status_code=400, detail="KB ID is required")
    services["kb_services"].delete_kb_by_id(kb_id)
    return JSONResponse(content={"message": "KB deleted"})

@router.get("/kb/documents")
async def get_documents(kb_id: str = Header(..., alias="KB-ID"), services: dict = Depends(get_services)):
    documents = services["kb_services"].get_docs_by_kbId(kb_id)
    return JSONResponse(content={"documents": documents})

@router.post("/kb/extract")
async def extract(
    file: Optional[UploadFile] = File(None),
    kb_id: Optional[str] = Form(None),
    request: Request = None,
    services: dict = Depends(get_services)
):
    extraction_service = ExtractionService(services["db"], services["uid"])
    
    if file:
        if file.filename.lower().endswith('.pdf'):
            return await extraction_service.extract_from_pdf(file, kb_id, services["uid"], services["kb_services"])
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    elif request:
        data = await request.json()
        kb_id = data.get('kbId')
        url = data.get('url')
        endpoint = data.get('endpoint', 'scrape')
        
        def generate():
            yield from extraction_service.extract_from_url(url, kb_id, endpoint, services["kb_services"])

        return StreamingResponse(generate(), media_type='text/event-stream')
    else:
        raise HTTPException(status_code=400, detail="No file or URL provided")
    
@router.post("/kb/embed")
async def embed(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    content = data.get('content')
    urls = data.get('urls')
    highlights = data.get('highlights')
    doc_id = data.get('id')
    kb_id = data.get('kbId')
    source = data.get('source')
    if content:
        kb_doc = services["kb_services"].chunk_and_embed_content(source, kb_id, doc_id, highlights, content=content)
    else:
        kb_doc = services["kb_services"].chunk_and_embed_content(source, kb_id, doc_id, highlights, urls=urls)
    return JSONResponse(content={"kb_doc": kb_doc})

@router.delete("/kb/documents")
async def delete_document(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    doc_id = data.get('docId')
    if not doc_id:
        raise HTTPException(status_code=400, detail="Doc ID is required")
    services["kb_services"].delete_doc_by_id(doc_id)
    return JSONResponse(content={"message": "Document deleted"})

@router.post("/kb/save_doc")
async def save_document(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    kb_id = data.get('kbId')
    urls = data.get('urls')
    content = data.get('content')
    highlights = data.get('highlights')
    doc_id = data.get('id')
    source = data.get('source')

    if content:
        result = services["kb_services"].create_kb_doc_in_db(kb_id, source, 'pdf', highlights, doc_id, content=content)
    else:
        result = services["kb_services"].create_kb_doc_in_db(kb_id, source, 'url', highlights, doc_id, urls=urls)
    
    if result == 'not_found':
        raise HTTPException(status_code=404, detail="Document not found")
    else:
        return JSONResponse(content={"message": "Text doc saved", "kb_doc": result})