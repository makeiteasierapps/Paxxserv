import os
import base64
import asyncio
from werkzeug.utils import secure_filename

class LocalStorageService:
    is_local = os.getenv('LOCAL_DEV') == 'true'
    base_path = 'mnt/media_storage' if not is_local else os.path.join(os.getcwd(), 'media_storage')

    @staticmethod
    async def upload_file_async(file, uid, folder, file_name=None):
        return await LocalStorageService._upload_file_async(file, uid, folder, file_name)

    @staticmethod
    async def _upload_file_async(file, uid, folder, file_name=None):
        try:
            # Handle different file types
            if hasattr(file, 'read'):
                if asyncio.iscoroutinefunction(file.read):
                    # Handle async file-like object (including FastAPI's UploadFile)
                    contents = await file.read()
                    original_filename = file.filename
                else:
                    # Handle synchronous file-like object
                    contents = file.read()
                    original_filename = file_name
            elif isinstance(file, str):
                # Handle base64 string
                contents = base64.b64decode(file)
                original_filename = 'file.bin'  # Default name for base64 input
            elif isinstance(file, bytes):
                # Handle bytes
                contents = file
                original_filename = file_name or 'file.bin'
            else:
                print("Unsupported file type")
                return None

            # Use the original filename, but secure it
            safe_filename = secure_filename(original_filename)
            
            relative_path = os.path.join('users', uid, folder)
            full_path = os.path.join(relative_path, safe_filename)
            local_full_path = os.path.join(LocalStorageService.base_path, full_path)

            # Ensure the directory exists
            os.makedirs(os.path.dirname(local_full_path), exist_ok=True)

            # Write the file content
            with open(local_full_path, 'wb') as f:
                f.write(contents)

            return {
                'path': full_path,
            }
        except Exception as e:
            print(f"Error in upload_file: {str(e)}")
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