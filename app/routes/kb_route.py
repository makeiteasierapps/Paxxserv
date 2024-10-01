from fastapi import APIRouter, Depends, HTTPException, Header, Request, File, UploadFile
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.KbDocumentService import KbDocumentService
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService
from app.services.ColbertService import ColbertService
from app.agents.OpenAiClient import OpenAiClient

router = APIRouter()

def get_services(dbName: str = Header(...), uid: str = Header(...)):
    mongo_client = MongoDbClient(dbName)
    db = mongo_client.connect()
    kb_service = KnowledgeBaseService(db, uid)
    openai_client = OpenAiClient(db, uid)
    return {
        "db": db,
        "uid": uid,
        "kb_service": kb_service,
        "openai_client": openai_client
    }

@router.get("/kb")
async def get_kb_list(services: dict = Depends(get_services)):
    kb_list = services["kb_service"].get_kb_list(services["uid"])
    return JSONResponse(content=kb_list)

@router.post("/kb")
async def create_kb(request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    new_kb_details = services["kb_service"].create_new_kb(services["uid"], data.get('name'), data.get('objective'))
    return JSONResponse(content=new_kb_details)

@router.delete("/kb/{kb_id}")
async def delete_kb(kb_id: str, services: dict = Depends(get_services)):
    if not kb_id:
        raise HTTPException(status_code=400, detail="KB ID is required")
    
    index_path = services["kb_service"].set_kb_id(kb_id)
    colbert_service = ColbertService(index_path)
    services["kb_service"].set_colbert_service(colbert_service)
    services["kb_service"].delete_kb_by_id(kb_id)
    return JSONResponse(content={"message": "KB deleted"})

@router.get("/kb/{kb_id}/documents")
async def get_documents(kb_id: str, services: dict = Depends(get_services)):
    kb_doc_service = KbDocumentService(services["db"], kb_id)
    documents = kb_doc_service.get_docs_by_kbId()
    return JSONResponse(content={"documents": documents})

@router.post("/kb/{kb_id}/extract")
async def extract(
    kb_id: str,
    file: Optional[UploadFile] = File(None),
    request: Request = None,
    services: dict = Depends(get_services)
):
    kb_doc_service = KbDocumentService(services["db"], kb_id, openai_client=services["openai_client"])
    extraction_service = ExtractionService(services["db"], services["uid"], kb_doc_service)
    
    if file:
        if file.filename.lower().endswith('.pdf'):
            kb_doc = await extraction_service.extract_from_pdf(file, kb_id)
            return JSONResponse(content=kb_doc)
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    else:
        data = await request.json()
        url = data.get('url')
        endpoint = data.get('endpoint', 'scrape')
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required when not uploading a file")
        
        kb_doc = extraction_service.extract_from_url(url, endpoint)
        return JSONResponse(content=kb_doc)

@router.delete("/kb/{kb_id}/documents/page")
async def delete_page(kb_id: str, request: Request, services: dict = Depends(get_services)):
    data = await request.json()
    doc_id = data.get('docId')
    page_source = data.get('pageSource')
    
    if not page_source:
        raise HTTPException(status_code=400, detail="Page source is required")
    
    kb_doc_service = KbDocumentService(services["db"], kb_id)
    is_embedded = kb_doc_service.is_document_embedded(doc_id, page_source)
    kb_doc_service.delete_page_by_source(doc_id, page_source)
    if is_embedded:
        services["kb_service"].set_kb_id(kb_id)
        index_path = services["kb_service"].index_path
        colbert_service = ColbertService(index_path)
        colbert_service.delete_document_from_index([page_source])
    
    return JSONResponse(content={"message": "Page deleted", "was_embedded": is_embedded})

@router.delete("/kb/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str, services: dict = Depends(get_services)):
    kb_doc_service = KbDocumentService(services["db"], kb_id)
    
    # Delete the document and get embedded sources
    embedded_sources = kb_doc_service.delete_doc_by_id(doc_id)

    # If there are embedded sources, delete them from the Colbert index
    if embedded_sources:
        services["kb_service"].set_kb_id(kb_id)
        index_path = services["kb_service"].index_path
        colbert_service = ColbertService(index_path)
        
        # Delete all embedded sources at once
        colbert_service.delete_document_from_index(embedded_sources)
    
    return JSONResponse(content={
        "message": "Document deleted",
        "embedded_sources_deleted": embedded_sources
    })

