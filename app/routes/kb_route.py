import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request, File, UploadFile, Form
from fastapi.responses import JSONResponse
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
    request: Request = None,
    kb_id: Optional[str] = Form(None, alias="kbId"),
    services: dict = Depends(get_services)
):
   
    extraction_service = ExtractionService(services["db"], services["uid"])
    
    if file:
        if file.filename.lower().endswith('.pdf'):
            kb_doc = await extraction_service.extract_from_pdf(file, kb_id, services["kb_services"])
            return JSONResponse(content=kb_doc)
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    else:
        try:
            data = await request.json()
            kb_id = data.get('kbId')
            url = data.get('url')
            endpoint = data.get('endpoint', 'scrape')
            
            if not url:
                raise HTTPException(status_code=400, detail="URL is required when not uploading a file")
            
            kb_doc = extraction_service.extract_from_url(url, kb_id, endpoint, services["kb_services"])
            return JSONResponse(content=kb_doc)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON data")

@router.post("/kb/embed")
async def embed(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    content = data.get('content')
    kb_id = data.get('kbId')
    source = data.get('source')
    doc_type = data.get('docType')
    doc_id = data.get('id')

    kb_service = services["kb_services"]
    
    # Process content with ColbertService
    results = kb_service.process_colbert_content(kb_id, doc_id, content)
    
    if results.get('created', False):
        print(f"New index created at: {results['index_path']}")
    else:
        print("Documents added to existing index")

    # Generate summaries
    summaries = kb_service.generate_summaries(content)

    # Update the database
    kb_doc = kb_service.update_kb_document(kb_id, source, doc_type, content, summaries, doc_id)

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
    doc_id = data.get('id')
    source = data.get('source')

    if content:
        result = services["kb_services"].create_kb_doc_in_db(kb_id, source, 'pdf', doc_id, content=content)
    else:
        result = services["kb_services"].create_kb_doc_in_db(kb_id, source, 'url', doc_id, urls=urls)
    
    if result == 'not_found':
        raise HTTPException(status_code=404, detail="Document not found")
    else:
        return JSONResponse(content={"message": "Text doc saved", "kb_doc": result})