from datetime import datetime
from json import JSONEncoder
from bson import ObjectId

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        # Add more custom serialization rules here as needed
        return super().default(obj)