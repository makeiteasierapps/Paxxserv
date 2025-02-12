from uuid import uuid4
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.KbDocumentService import KbDocumentService
from app.services.ColbertService import ColbertService


async def process_document(sio, sid, data, mongo_client):
    try:
        uid = data.get('uid')
        kb_id = data.get('kbId')
        doc_id = data.get('id')
        operation = data.get('operation', 'embed')

        db = mongo_client.db
        kb_service = KnowledgeBaseService(db, uid, kb_id)
        kb_document_service = KbDocumentService(db, kb_id)

        if operation == 'save':
            documents_to_change = data.get('documentsToChange', None)
            if not doc_id:
                await sio.emit('error', {"error": "Doc ID is required for save operation"}, room=sid)
                return
            result = await save_document(kb_document_service, documents_to_change, doc_id)
            await sio.emit('save_complete', {"status": "success", "result": result}, room=sid)
        elif operation == 'embed':
            process_id = str(uuid4())
            index_path = kb_service.get_index_path()
            colbert_service = ColbertService(index_path=index_path, uid=uid)
            kb_document_service.set_colbert_service(colbert_service)

            sio.start_background_task(
                process_and_update_client,
                sio,
                sid,
                process_id,
                kb_document_service,
                doc_id
            )
            await sio.emit('process_started', {"process_id": process_id}, room=sid)
        else:
            await sio.emit('error', {"error": f"Invalid operation: {operation}"}, room=sid)

    except Exception as e:
        await sio.emit('error', {"error": str(e)}, room=sid)

async def save_document(kb_document_service, content, doc_id):
    return kb_document_service.save_documents(content, doc_id)

async def process_and_update_client(
    sio,
    sid,
    process_id,
    kb_document_service,
    doc_id
):
    try:
        await sio.emit('process_started', {"process_id": process_id, "status": "Processing started"}, room=sid)
        kb_doc = kb_document_service.embed_document(doc_id)
        await sio.emit('process_complete', {"process_id": process_id, "status": "success", "kb_doc": kb_doc}, room=sid)
    except Exception as e:
        await sio.emit('process_error', {"process_id": process_id, "status": "error", "message": str(e)}, room=sid)

def setup_document_handlers(sio, mongo_client):
    @sio.on('process_document')
    async def process_document_handler(sid, data):
        await process_document(sio, sid, data, mongo_client)