import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Optional
from dotenv import load_dotenv
from app.utils.custom_json_encoder import CustomJSONEncoder
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService
from app.services.ColbertService import ColbertService
from app.agents.OpenAiClient import OpenAiClient

load_dotenv()

router = APIRouter()

def get_base_services(
    dbName: str = Header(...),
    uid: str = Header(...)
):
    mongo_client = MongoDbClient(dbName)
    db = mongo_client.connect()
    return {
        "mongo_client": mongo_client,
        "db": db,
        "uid": uid
    }

def get_db(dbName: str = Header(...)):
    mongo_client = MongoDbClient(dbName)
    return mongo_client.connect()

def get_uid(uid: str = Header(...)):
    return uid

def get_kb_service(services: dict = Depends(get_base_services)):
    return KnowledgeBaseService(services["db"], services["uid"])

def get_colbert_service(index_path: Optional[str] = None):
    return ColbertService(index_path)

def get_openai_client(services: dict = Depends(get_base_services)):
    return OpenAiClient(services["db"], services["uid"])

@router.get("/kb")
async def get_kb_list(
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    uid: str = Depends(get_uid)
):
    kb_list = kb_service.get_kb_list(uid)
    json_kb_list = jsonable_encoder(kb_list)
    json_str = json.dumps(json_kb_list, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))

@router.post("/kb")
async def create_kb(
    request: Request,
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    uid: str = Depends(get_uid)
):
    data = await request.json()
    name = data.get('name')
    objective = data.get('objective')
    new_kb_details = kb_service.create_new_kb(uid, name, objective)
    json_kb_details = jsonable_encoder(new_kb_details)
    json_str = json.dumps(json_kb_details, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))

@router.delete("/kb/{kb_id}")
async def delete_kb(
    kb_id: str,
    kb_service: KnowledgeBaseService = Depends(get_kb_service)
):
    if not kb_id:
        raise HTTPException(status_code=400, detail="KB ID is required")
    kb_service.delete_kb_by_id(kb_id)
    return JSONResponse(content={"message": "KB deleted"})

@router.get("/kb/{kb_id}/documents")
async def get_documents(
    kb_id: str,
    kb_service: KnowledgeBaseService = Depends(get_kb_service)
):
    kb_service.set_kb_id(kb_id)
    documents = kb_service.get_docs_by_kbId()
    return JSONResponse(content={"documents": documents})

@router.post("/kb/{kb_id}/extract")
async def extract(
    kb_id: str,
    file: Optional[UploadFile] = File(None),
    request: Request = None,
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    db: str = Depends(get_base_services),
    uid: str = Depends(get_base_services)
):
    extraction_service = ExtractionService(db, uid)
    kb_service.set_kb_id(kb_id)

    if file:
        if file.filename.lower().endswith('.pdf'):
            kb_doc = await extraction_service.extract_from_pdf(file, kb_id, kb_service)
            return JSONResponse(content=kb_doc)
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    else:
        try:
            data = await request.json()
            url = data.get('url')
            endpoint = data.get('endpoint', 'scrape')
            
            if not url:
                raise HTTPException(status_code=400, detail="URL is required when not uploading a file")
            
            kb_doc = extraction_service.extract_from_url(url, endpoint, kb_service)
            return JSONResponse(content=kb_doc)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON data")

@router.post("/kb/{kb_id}/embed")
async def embed(
    kb_id: str,
    request: Request,
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    openai_client: OpenAiClient = Depends(get_openai_client)
):
    data = await request.json()
    content = data.get('content')
    source = data.get('source')
    doc_type = data.get('docType')
    doc_id = data.get('id')

    index_path = kb_service.set_kb_id(kb_id)
    colbert_service = get_colbert_service(index_path)
    kb_service.set_colbert_service(colbert_service)
    kb_service.set_openai_client(openai_client)
    
    # Process content with ColbertService
    results = kb_service.process_colbert_content(doc_id, content)
    
    if results.get('created', False):
        print(f"New index created at: {results['index_path']}")
    else:
        print("Documents added to existing index")

    # Generate summaries
    summaries = kb_service.generate_summaries(content)

    # Update the database
    kb_doc = kb_service.update_kb_document(source, doc_type, content, summaries, doc_id)

    return JSONResponse(content={"kb_doc": kb_doc})

@router.delete("/kb/{kb_id}/documents")
async def delete_document(
    kb_id: str,
    request: Request,
    kb_service: KnowledgeBaseService = Depends(get_kb_service)
):
    data = await request.json()
    doc_id = data.get('docId')
    if not doc_id:
        raise HTTPException(status_code=400, detail="Doc ID is required")
    
    index_path = kb_service.set_kb_id(kb_id)
    colbert_service = get_colbert_service(index_path)
    kb_service.set_colbert_service(colbert_service)
    
    kb_service.delete_doc_by_id(doc_id)
    return JSONResponse(content={"message": "Document deleted"})

# This route has not been refactored to remove the url field yet.
@router.post("/kb/{kb_id}/save_doc")
async def save_document(
    kb_id: str,
    request: Request,
    kb_service: KnowledgeBaseService = Depends(get_kb_service)
):
    data = await request.json()
    urls = data.get('urls')
    content = data.get('content')
    doc_id = data.get('id')
    source = data.get('source')

    kb_service.set_kb_id(kb_id)

    if content:
        result = kb_service.update_kb_doc_in_db(source, 'pdf', doc_id, content=content)
    else:
        result = kb_service.update_kb_doc_in_db(source, 'url', doc_id, urls=urls)
    
    if result == 'not_found':
        raise HTTPException(status_code=404, detail="Document not found")
    else:
        return JSONResponse(content={"message": "Text doc saved", "kb_doc": result})