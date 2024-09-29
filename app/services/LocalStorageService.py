import os
from dotenv import load_dotenv
import base64
import asyncio
from werkzeug.utils import secure_filename

load_dotenv()

class LocalStorageService:
    is_local = os.getenv('LOCAL_DEV') == 'true'
    base_path = '/mnt/media_storage' if not is_local else os.path.join(os.getcwd(), 'media_storage')

    @staticmethod
    async def download_file_async(path):
        try:
            full_path = os.path.join(LocalStorageService.base_path, path.lstrip('/'))
            if not os.path.exists(full_path):
                print(f"File not found: {full_path}")
                return None

            # Read the file content asynchronously
            loop = asyncio.get_event_loop()
            with open(full_path, 'rb') as file:
                contents = await loop.run_in_executor(None, file.read)

            return contents

        except Exception as e:
            print(f"Error in download_file_async: {str(e)}")
            return None
    
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

            return full_path.lstrip('/')
            
        except Exception as e:
            print(f"Error in upload_file: {str(e)}")
            return None
        
    @staticmethod
    #need to delete the thumbnail if it exists
    def delete_image(path):
        full_path = os.path.join(LocalStorageService.base_path, path.lstrip('/'))
        if os.path.exists(full_path):
            os.remove(full_path)

    @staticmethod
    def fetch_all_images(uid, folder):
        relative_path = os.path.join('users', uid, folder)
        path = os.path.join(LocalStorageService.base_path, relative_path)
        if not os.path.exists(path):
            return []
        
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        files = [file for file in os.listdir(path) 
                 if os.path.isfile(os.path.join(path, file)) and 
                 file.lower().endswith(image_extensions)]
        
        return [{'path': f'{relative_path}/{file}'} for file in files]