from io import BytesIO
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

    def update_user_avatar(self, uid, file_content):
        print(uid)
        # Convert the incoming file to a BytesIO object
        file_data = BytesIO(file_content)
        file_data.seek(0)

        # Create a custom file-like object with a filename attribute
        class CustomFile:
            def __init__(self, file_data, filename):
                self.file_data = file_data
                self.filename = filename

            def read(self):
                return self.file_data.read()

        custom_file = CustomFile(file_data, 'avatar.png')

        avatar_url = LocalStorageService.upload_file(custom_file, uid, 'profile_images')
        print(avatar_url)
        self.db['users'].update_one(
            {'_id': uid},
            {'$set': {'avatar_url': avatar_url}},
            upsert=True
        )
        return avatar_url