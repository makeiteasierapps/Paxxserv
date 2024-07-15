from flask import Flask, request, jsonify
import logging
from ragatouille import RAGPretrainedModel
app = Flask(__name__)

@app.route('/create_index', methods=['POST'])
def create_index():
    try:
        data = request.get_json()
        project_id = data.get('projectId')
        name = data.get('name')
        documents = data.get('documents')
        # Extract parameters from request
        index_prefix = f'/mnt/ssd/indexes/{project_id}/ragatouille/'
        RAG = RAGPretrainedModel.from_pretrained(pretrained_model_name_or_path="colbert-ir/colbertv2.0", index_root=index_prefix)
        RAG.index(
            collection=documents,
            index_name=name,
            split_documents=False,
            use_faiss=True,
        )
        return jsonify({"message": "Index created successfully"})
    except KeyError as e:
        logging.error("Missing key in the request: %s", str(e))
        return jsonify({"error": f"Missing key in the request: {str(e)}"}), 400
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/update_index', methods=['POST'])
def update_index():
    data = request.get_json()
    project_id = data.get('projectId')
    name = data.get('name')
    new_documents = data.get('documents')
    path_to_index = f'/mnt/ssd/indexes/{project_id}/ragatouille/colbert/indexes/{name}'
    RAG = RAGPretrainedModel.from_index(path_to_index)
    RAG.add_to_index(new_documents, use_faiss=True)
    return jsonify({"message": "Index updated successfully"})

@app.route('/query_index', methods=['POST'])
def query_index():
    data = request.get_json()
    project_id = data.get('projectId')
    name = data.get('name')
    query = data.get('query')
    path_to_index = f'/mnt/ssd/indexes/{project_id}/ragatouille/colbert/indexes/{name}'
    RAG = RAGPretrainedModel.from_index(path_to_index)

    k = 10
    results = RAG.search(query, k=k)
    print(results)
    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
