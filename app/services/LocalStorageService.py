import os
import base64
import uuid
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

class LocalStorageService:
    local_dev = os.getenv('LOCAL_DEV', 'false').lower() == 'true'
    media_storage_url = os.getenv('MEDIA_STORAGE_URL', 'http://myserver.local/mnt/media_storage')
    base_path = media_storage_url if local_dev else '/mnt/media_storage'
    
    @staticmethod
    def directory_exists(path):
        if LocalStorageService.local_dev:
            url = f"{LocalStorageService.base_path}/{path}"
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        else:
            return os.path.isdir(os.path.join(LocalStorageService.base_path, path))
    
    @staticmethod
    def upload_image(image, uid, folder):
        try:
            unique_filename = f"{uuid.uuid4()}.jpg"
            relative_path = os.path.join('users', uid, folder)
            full_path = os.path.join(relative_path, unique_filename)

            if LocalStorageService.local_dev:
                url = f"{LocalStorageService.base_path}/{full_path}"
                response = requests.put(url, data=image.read(), timeout=10)
                if response.status_code != 201:
                    raise Exception(f"Failed to upload image: {response.text}")
            else:
                local_full_path = os.path.join(LocalStorageService.base_path, full_path)
                os.makedirs(os.path.dirname(local_full_path), exist_ok=True)
                with open(local_full_path, 'wb') as f:
                    f.write(image.read())

            image.seek(0)
            base64_image = base64.b64encode(image.read()).decode('utf-8')

            return {
                'path': f'/{full_path}',
                'base64_data': base64_image
            }
        except Exception as e:
            print(f"Error in upload_image: {str(e)}")
            return None
    
    @staticmethod
    def delete_image(path):
        if LocalStorageService.local_dev:
            url = f"{LocalStorageService.base_path}/{path.lstrip('/')}"
            response = requests.delete(url, timeout=10)
            if response.status_code != 204:
                raise Exception(f"Failed to delete image: {response.text}")
        else:
            full_path = os.path.join(LocalStorageService.base_path, path.lstrip('/'))
            if os.path.exists(full_path):
                os.remove(full_path)

    @staticmethod
    def fetch_all_images(uid, folder):
        relative_path = os.path.join('users', uid, folder)
        if LocalStorageService.local_dev:
            url = f"{LocalStorageService.base_path}/{relative_path}"
            response = requests.get(url, timeout=10)
            print(response)
            print(response.text)
            if response.status_code == 200:
                files = response.json()  # Assuming the response is a JSON list of file names
            else:
                raise Exception(f"Failed to fetch images: {response.text}")
        else:
            path = os.path.join(LocalStorageService.base_path, relative_path)
            files = os.listdir(path) if os.path.exists(path) else []
        
        return [{'path': f'{relative_path}/{file}'} for file in files]

    @staticmethod
    def upload_file(file, uid, folder):
        original_filename = secure_filename(file.filename) if file.filename else f"{uuid.uuid4()}"
        relative_path = os.path.join('users', uid, folder)
        full_path = os.path.join(relative_path, original_filename)

        if LocalStorageService.local_dev:
            url = f"{LocalStorageService.base_path}/{full_path}"
            response = requests.put(url, data=file.read(), timeout=10)
            if response.status_code != 201:
                raise Exception(f"Failed to upload file: {response.text}")
        else:
            local_full_path = os.path.join(LocalStorageService.base_path, full_path)
            os.makedirs(os.path.dirname(local_full_path), exist_ok=True)
            file.save(local_full_path)

        return f'/{full_path}'

# Ensure the local storage directory exists if we're not in local dev mode
if not LocalStorageService.local_dev:
    os.makedirs(LocalStorageService.base_path, exist_ok=True)