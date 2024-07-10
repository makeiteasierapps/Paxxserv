from dotenv import load_dotenv
from flask import  Blueprint, request, jsonify, g
from app.agents.BossAgent import BossAgent
from app.agents.ContentProcessor import ContentProcessor
from app.services.MomentService import MomentService
from app.services.MongoDbClient import MongoDbClient

load_dotenv()
moment_bp = Blueprint('moment_bp', __name__)

@moment_bp.before_request
def initialize_services():
    if request.method == 'OPTIONS':
        return ('', 204)
    db_name = request.headers.get('dbName', 'paxxium')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.moment_service = MomentService(db)

@moment_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@moment_bp.route('/moments', methods=['GET'])
def handle_fetch_moments():
    # Get all moments from the database
    all_moments = g.moment_service.get_all_moments()
    response = jsonify(all_moments)
    response.status_code = 200
    return response
    
@moment_bp.route('/moments', methods=['POST'])
def handle_add_moment():
    """
    This function handles the addition of a new moment.
    """
    content_processor = ContentProcessor(model='gpt-4o')
    new_moment = request.json['newMoment']
    new_moment = {**new_moment, **content_processor.extract_content(new_moment)}

    # Add the moment to the database
    new_moment = g.moment_service.add_moment(new_moment)
    # Prepare snapshot for embeddings
    combined_content = f"Transcript: {new_moment['transcript']}\nAction Items:\n" + "\n".join(new_moment['actionItems']) + f"\nSummary: {new_moment['summary']}"
    snapshot_data = new_moment.copy()
    # Create and add embeddings to the snapshot
    snapshot_data['embeddings'] = BossAgent.embed_content(combined_content)
    # Add the snapshot to the database
    g.moment_service.create_snapshot(snapshot_data)

    response = jsonify(new_moment)
    
    response.status_code = 200
    
    return response

@moment_bp.route('/moments', methods=['PUT'])
def handle_update_moment():
    content_processor = ContentProcessor(model='gpt-4o')
    current_moment = request.json['moment']
    moment_id = current_moment['momentId']
    current_snapshot = {**current_moment, **content_processor.extract_content(current_moment)}
    current_snapshot['momentId'] = moment_id
    previous_snapshot = g.moment_service.get_previous_snapshot(moment_id)

    # Combine and embed the current snapshot
    combined_content = f"Transcript: {current_moment['transcript']}\nAction Items:\n" + "\n".join(current_snapshot['actionItems']) + f"\nSummary: {current_snapshot['summary']}"
    current_snapshot['embeddings'] = BossAgent.embed_content(combined_content)
    
    # Create snapshot in the db
    g.moment_service.create_snapshot(current_snapshot)

    # diff the current snapshot with the previous snapshot
    new_snapshot = content_processor.diff_snapshots(previous_snapshot, current_snapshot)
    new_snapshot.update({
        'momentId': moment_id,
        'date': current_moment['date'],
        'transcript': current_moment['transcript']
    })

    new_snapshot['transcript'] = g.moment_service.update_moment(new_snapshot)
    response = jsonify(new_snapshot)
    response.status_code = 200
    return response

@moment_bp.route('/moments', methods=['DELETE'])
def handle_delete_moment():
    moment_id = request.json['id']
    g.moment_service.delete_moment(moment_id)
    response = jsonify({'message': 'Moment Deleted'})
    response.status_code = 200
    return response
