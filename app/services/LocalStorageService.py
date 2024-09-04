import os
import uuid
from werkzeug.utils import secure_filename

class LocalStorageService:
    BASE_PATH = '/mnt/media_storage'

    @staticmethod
    def upload_image(image, uid, folder):
        unique_filename = f"{uuid.uuid4()}.jpg"
        path = os.path.join(LocalStorageService.BASE_PATH, 'users', uid, folder)
        os.makedirs(path, exist_ok=True)
        full_path = os.path.join(path, unique_filename)
        with open(full_path, 'wb') as f:
            f.write(image.read())
        return f'/users/{uid}/{folder}/{unique_filename}'

    @staticmethod
    def delete_image(path):
        full_path = os.path.join(LocalStorageService.BASE_PATH, path.lstrip('/'))
        if os.path.exists(full_path):
            os.remove(full_path)

    @staticmethod
    def fetch_all_images(uid, folder):
        path = os.path.join(LocalStorageService.BASE_PATH, 'users', uid, folder)
        if not os.path.exists(path):
            return []
        files = os.listdir(path)
        return [{'url': f'/users/{uid}/{folder}/{file}', 'path': f'users/{uid}/{folder}/{file}'} for file in files]

    @staticmethod
    def upload_file(file, uid, folder):
        original_filename = secure_filename(file.filename) if file.filename else f"{uuid.uuid4()}"
        path = os.path.join(LocalStorageService.BASE_PATH, 'users', uid, folder)
        os.makedirs(path, exist_ok=True)
        full_path = os.path.join(path, original_filename)
        file.save(full_path)
        return f'/users/{uid}/{folder}/{original_filename}'