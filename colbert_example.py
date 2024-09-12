import time
from ragatouille import RAGPretrainedModel
from ragatouille.utils import get_wikipedia_page

def build_index():
    start_time = time.time()  # Start timing
    RAG = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")
    my_documents = [get_wikipedia_page("Hayao_Miyazaki"), get_wikipedia_page("Studio_Ghibli")]

    document_ids = ["miyazaki", "ghibli"]
    document_metadatas = [
        {"entity": "person", "source": "wikipedia"},
        {"entity": "organisation", "source": "wikipedia"},
    ]
    RAG.index(
        index_name="my_index_with_ids_and_metadata",
        collection=my_documents,
        document_ids=document_ids,
        document_metadatas=document_metadatas,
    )
    end_time = time.time()  # End timing
    print(f"Build index took {end_time - start_time:.2f} seconds")  # Print the elapsed time

if __name__ == "__main__":
    build_index()