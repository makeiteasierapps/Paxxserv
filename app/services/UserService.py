from .LocalStorageService import LocalStorageService

class UserService:
    def __init__(self, db):
        self.db = db

    def get_user(self, uid):
        return self.db['users'].find_one({'_id': uid})

    def create_user(self, uid, user_data):
        user_data['_id'] = uid
        return self.db['users'].insert_one(user_data)

    def update_user(self, uid, updates):
        return self.db['users'].update_one({'_id': uid}, {'$set': updates})

    def delete_user(self, uid):
        return self.db['users'].delete_one({'_id': uid})

    async def update_user_avatar(self, uid, file):
        path = await LocalStorageService.upload_file_async(file, uid, 'profile_images')
        file_path = path['path']
        self.db['users'].update_one(
            {'_id': uid},
            {'$set': {'avatar_path': file_path}},
            upsert=True
        )
        return file_path