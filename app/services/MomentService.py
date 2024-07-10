from bson.objectid import ObjectId

# None of this is user specific
class MomentService:
    def __init__(self, db):
        self.db = db

    def get_all_moments(self):
        moments_collection = self.db['moments']
        moments = list(moments_collection.find({}))
        for moment in moments:
            moment['id'] = str(moment.pop('_id'))
        return moments

    def get_previous_snapshot(self, moment_id):
        snapshots_collection = self.db['snapshots']
        snapshots = list(snapshots_collection.find({'momentId': moment_id}))
        if len(snapshots) > 0:
            most_recent_snapshot = snapshots[-1]
            most_recent_snapshot['id'] = str(most_recent_snapshot.pop('_id'))
            return most_recent_snapshot
        else:
            return None
        
    def create_snapshot(self, snapshot_data):
        snapshots_collection = self.db['snapshots']
        snapshots_collection.insert_one(snapshot_data)
        # Convert _id to string and rename it to id
        snapshot_data['id'] = str(snapshot_data.pop('_id'))
        return snapshot_data

    def add_moment(self, moment_data):
        moments_collection = self.db['moments']
        moments_collection.insert_one(moment_data)
        # Convert _id to string and rename it to id
        moment_data['momentId'] = str(moment_data.pop('_id'))
        return moment_data

    def update_moment(self, moment_data):
        moments_collection = self.db['moments']
        moment_id = moment_data['momentId']

        # Fetch the current transcript
        current_moment = moments_collection.find_one({'_id': ObjectId(moment_id)})
        if current_moment:
            current_transcript = current_moment.get('transcript', '')
            new_transcript = current_transcript + moment_data['transcript']

            update_data = {
                '$set': {
                    'actionItems': moment_data['actionItems'],
                    'summary': moment_data['summary'],
                    'transcript': new_transcript 
                }
            }
            moments_collection.update_one({'_id': ObjectId(moment_id)}, update_data)
            return new_transcript
        else:
            print("Moment not found.")
            return 0
        
    def delete_moment(self, moment_id):
            moments_collection = self.db['moments']
            snapshots_collection = self.db['snapshots']
            result = moments_collection.delete_one({'_id': ObjectId(moment_id)})
            snapshots_collection.delete_many({'momentId': moment_id})
            return result.deleted_count

