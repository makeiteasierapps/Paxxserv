import uuid
from canopy.tokenizer import Tokenizer
from canopy.models.data_models import Document
from canopy.knowledge_base.models import KBEncodedDocChunk
from canopy.knowledge_base.chunker.recursive_character import RecursiveCharacterChunker
from .OpenAiClientBase import OpenAiClientBase

class DocumentManager(OpenAiClientBase):
    def __init__(self, db, uid):
        super().__init__(db, uid)
        Tokenizer.initialize()
        self.tokenizer = Tokenizer()

    def chunkify(self, source, content=None, chunks=None):
        if content and self.tokenizer.token_count(content) < 1000:
            return [Document(id=str(uuid.uuid4()), text=content, source=source)]
        if chunks is None:
            doc_id = str(uuid.uuid4())
            chunker = RecursiveCharacterChunker(chunk_size=450)
            chunks = chunker.chunk_single_document(Document(id=doc_id, text=content, source=source))
        else:
            chunks = [Document(id=chunk['id'], text=chunk['text'], source=source) for chunk in chunks]
        return chunks
    
    def embed_chunks(self, chunks):
        encoded_chunks = []
        for chunk in chunks:
            embeddings = self.embed_content(chunk.text)
            encoded_chunk = KBEncodedDocChunk(
                id=chunk.id,
                text=chunk.text,
                document_id=chunk.id,
                values=embeddings,
                metadata=chunk.metadata if hasattr(chunk, 'metadata') else {},
                source=chunk.source if hasattr(chunk, 'source') else None
            )
            
            record = encoded_chunk.to_db_record()
            encoded_chunks.append(record)
        return encoded_chunks

    def summarize_content(self, content):
        token_count = self.tokenizer.token_count(content)
        if token_count > 10000:
            # Summarize each chunk individually
            return "Content is too long to summarize."
        response = self.openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system', 
                    'content': 'You are a helpful assistant that summarizes the content of a document.'
                },
                {
                    'role': 'user',
                    'content': f'''
                    Please provide a detailed summary of the following document:
                    {content}
                    '''
                }
            ]
        )
        return response.choices[0].message.content
    