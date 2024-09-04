import os
import requests
import base64
import uuid
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

class LocalStorageService:
    LOCAL_DEV = os.getenv('LOCAL_DEV', 'false').lower() == 'true'
    MEDIA_STORAGE_URL = os.getenv('MEDIA_STORAGE_URL', 'http://myserver.local/mnt/media_storage')
    BASE_PATH = MEDIA_STORAGE_URL if LOCAL_DEV else '/mnt/media_storage'

    @staticmethod
    def upload_image(image, uid, folder):
        try:
            print(f"Starting upload for user {uid} in folder {folder}")
            unique_filename = f"{uuid.uuid4()}.jpg"
            relative_path = os.path.join('users', uid, folder)
            full_path = os.path.join(relative_path, unique_filename)
            
            print(f"Full path: {full_path}")
            print(f"Base path: {LocalStorageService.BASE_PATH}")

            # Ensure the directory exists
            create_dir_url = f"{LocalStorageService.BASE_PATH}/{relative_path}"
            print(f"Creating directory: {create_dir_url}")
            response = requests.request('MKCOL', create_dir_url, timeout=10)
            print(f"Directory creation response: {response.status_code} - {response.text}")

            # Read image data
            image_data = image.read()

            # Use HTTP PUT to upload file
            upload_url = f"{LocalStorageService.BASE_PATH}/{full_path}"
            print(f"Uploading to: {upload_url}")
            response = requests.put(upload_url, data=image_data, timeout=10)
            print(f"Upload response: {response.status_code} - {response.text}")

            if response.status_code != 201:
                raise Exception(f"Failed to upload image: {response.text}")

            # Encode the image data to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            return {
                'path': f'/{full_path}',
                'base64_data': base64_image
            }
        except Exception as e:
            print(f"Error in upload_image: {str(e)}")
            return None
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