import os
import base64
import uuid
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

class LocalStorageService:
    is_local = os.getenv('LOCAL_DEV') == 'true'
    base_path = '/mnt/media_storage' if not is_local else os.path.join(os.getcwd(), 'media_storage')
    
    @staticmethod
    def directory_exists(path):
        return os.path.isdir(os.path.join(LocalStorageService.base_path, path))
    
    @staticmethod
    def upload_image(image, uid, folder):
        try:
            unique_filename = f"{uuid.uuid4()}.jpg"
            relative_path = os.path.join('users', uid, folder)
            full_path = os.path.join(relative_path, unique_filename)
            local_full_path = os.path.join(LocalStorageService.base_path, full_path)

            os.makedirs(os.path.dirname(local_full_path), exist_ok=True)

            # Debug: Check the type of the image
            print(f"Type of image: {type(image)}")

            if isinstance(image, str):
                # Handle base64 string
                image_data = base64.b64decode(image)
                with open(local_full_path, 'wb') as f:
                    f.write(image_data)
            elif isinstance(image, bytes):
                # Handle bytes
                with open(local_full_path, 'wb') as f:
                    f.write(image)
            elif hasattr(image, 'read'):
                # Handle Blob (file-like object)
                with open(local_full_path, 'wb') as f:
                    f.write(image.read())
                image.seek(0)
            else:
                print("Unsupported image type")
                return None

            return {
                'path': full_path,
            }
        except Exception as e:
            print(f"Error in upload_image: {str(e)}")
            return None
    
    @staticmethod
    def delete_image(path):
        full_path = os.path.join(LocalStorageService.base_path, path.lstrip('/'))
        if os.path.exists(full_path):
            os.remove(full_path)

    @staticmethod
    def fetch_all_images(uid, folder):
        relative_path = os.path.join('users', uid, folder)
        path = os.path.join(LocalStorageService.base_path, relative_path)
        files = os.listdir(path) if os.path.exists(path) else []
        return [{'path': f'{relative_path}/{file}'} for file in files]

    @staticmethod
    def upload_file(file, uid, folder):
        original_filename = secure_filename(file.filename) if file.filename else f"{uuid.uuid4()}"
        relative_path = os.path.join('users', uid, folder)
        full_path = os.path.join(relative_path, original_filename)
        local_full_path = os.path.join(LocalStorageService.base_path, full_path)

        os.makedirs(os.path.dirname(local_full_path), exist_ok=True)
        file.save(local_full_path)

        return f'/{full_path}'

# Ensure the storage directory exists
os.makedirs(LocalStorageService.base_path, exist_ok=True)