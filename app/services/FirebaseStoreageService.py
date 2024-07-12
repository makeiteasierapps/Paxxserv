import uuid
from firebase_admin import storage

class FirebaseStorageService:
    @staticmethod
    def upload_image(image, uid, folder):
        bucket = storage.bucket()
        unique_filename = str(uuid.uuid4())
        blob = bucket.blob(f'users/{uid}/{folder}/{unique_filename}')
        file_data = image.read()
        blob.upload_from_string(file_data, content_type='image/jpeg')
        blob.make_public()
        return blob.public_url

    @staticmethod
    def delete_image(path):
        bucket = storage.bucket()
        blob = bucket.blob(path)
        blob.delete()

    @staticmethod
    def fetch_all_images(uid, folder):
        bucket = storage.bucket()
        folder_path = f'users/{uid}/{folder}/'
        blobs = bucket.list_blobs(prefix=folder_path)
        return [{'url': blob.public_url, 'path': blob.name} for blob in blobs]

    @staticmethod
    def upload_file(file, uid, folder):
        bucket = storage.bucket()
        unique_filename = str(uuid.uuid4())
        blob = bucket.blob(f'users/{uid}/{folder}/{unique_filename}')
        content_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
        file_data = file.read()
        blob.upload_from_string(file_data, content_type=content_type)
        blob.make_public()
        return blob.public_url