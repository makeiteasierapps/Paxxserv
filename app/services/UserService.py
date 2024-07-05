import os
import uuid
import base64
from dotenv import load_dotenv
from google.cloud import kms
from firebase_admin import storage

class UserService:
    def __init__(self, db):
        self.db = db

    def get_keys(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'open_key': 1})
        return user_doc['open_key']

    @staticmethod
    def crc32c(data: bytes) -> int:
        """
        Calculates the CRC32C checksum of the provided data.

        Args:
            data: the bytes over which the checksum should be calculated.

        Returns:
            An int representing the CRC32C checksum of the provided bytes.
        """
        import crcmod  # type: ignore
        import six  # type: ignore

        crc32c_fun = crcmod.predefined.mkPredefinedCrcFun("crc-32c")
        
        return crc32c_fun(six.ensure_binary(data))

    def encrypt(self, input_str):
        load_dotenv()
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        # Convert the input string to bytes
        plaintext_bytes = input_str.encode('utf-8')
        plaintext_crc32c = UserService.crc32c(plaintext_bytes)

        # Use the KMS API to encrypt the data.
        kms_client = kms.KeyManagementServiceClient()
        kms_key_name = os.environ.get("KMS_KEY_NAME")
        encrypt_response = kms_client.encrypt(request={'name': kms_key_name, 'plaintext': plaintext_bytes, 'plaintext_crc32c': plaintext_crc32c})
      
        # Integrity verification on encrypt_response.
        if not encrypt_response.verified_plaintext_crc32c:
            raise Exception("The request sent to the server was corrupted in-transit.")
        if not encrypt_response.ciphertext_crc32c == UserService.crc32c(encrypt_response.ciphertext):
            raise Exception("The response received from the server was corrupted in-transit.")

        # Parse it to a type that firebase likes, plus make decrypting easier
        ciphertext = encrypt_response.ciphertext
        ciphertext_str = base64.b64encode(ciphertext).decode('utf-8')

        return ciphertext_str

    def decrypt(self, key):
        load_dotenv()
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        
        kms_client = kms.KeyManagementServiceClient()
        kms_key_name = os.environ.get("KMS_KEY_NAME")

        # Decode the base64-encoded key to bytes
        ciphertext_bytes = base64.b64decode(key)
        decrypted_key_response = kms_client.decrypt(request={'name': kms_key_name, 'ciphertext': ciphertext_bytes})
        decrypted_key = decrypted_key_response.plaintext.decode('utf-8')

        return decrypted_key

    def get_profile(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'first_name': 1, 'last_name': 1, 'username': 1, 'avatar_url': 1, 'analysis': 1})
        
        if user_doc:
            user_doc.pop('_id')
        
        return user_doc
    
    def get_user_analysis(self, uid):
        user_doc = self.db['users'].find_one({'_id': uid}, {'analysis': 1})
        
        return user_doc

    @staticmethod
    def extract_data_for_prompt(answers):
        """ 
        Extracts the data from the answers dictionary and formats it for the prompt
        """
        prompt = ''
        for category, questions in answers.items():
            for question, answer in questions.items():
                prompt += f'{category}: {question} - Answer: {answer}\n'
        
        return prompt
    
    def prepare_analysis_prompt(self, uid):
        """
        Generates a prompt to analyze
        """
        
        q_a = self.load_profile_answers(uid)
        prompt = UserService.extract_data_for_prompt(q_a)

        return prompt
        
    def update_profile_answers(self, uid, data):
        """
        Update the question/answer map in the user's profile for MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """

        # Find the profile document by user ID reference
        profile_doc = self.db['profile'].find_one({'uid': uid})

        if profile_doc:
            # If the document exists, update it
            self.db['profile'].update_one({'uid': uid}, {'$set': {'questions': data}})
        else:
            # If no document exists for this user, create one
            self.db['profile'].insert_one({'uid': uid, 'questions': data})

        return {'message': 'User question/answers updated'}, 200
    
    def load_profile_answers(self, uid):
        """
        Fetches the question/answers map from the user's profile in MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """

        # Find the profile document by user ID reference
        profile_doc = self.db['profile'].find_one({'uid': uid}, {'questions': 1})

        if profile_doc and 'questions' in profile_doc:
            return profile_doc['questions']
        
        return {}
    
    def update_user_profile(self, uid, updates):
        users_collection = self.db['users']  # Access the 'users' collection
       
        if 'serp_key' in updates:
            updates['serp_key'] = self.encrypt(updates['serp_key'])

        if 'open_key' in updates:
            updates['open_key'] = self.encrypt(updates['open_key'])

        if 'news_topics' in updates:
            news_topics_list = [topic.lower().strip() for topic in updates['news_topics']]
            updates['news_topics'] = {"$addToSet": {"news_topics": {"$each": news_topics_list}}}

        user_doc = users_collection.find_one({"_id": uid})

        if user_doc:
            # Update existing user
            if 'news_topics' in updates:
                # Special handling for news_topics to use $addToSet for array elements
                news_topics_update = updates.pop('news_topics')
                users_collection.update_one({"_id": uid}, {"$set": updates, **news_topics_update})
            else:
                users_collection.update_one({"_id": uid}, {"$set": updates})
        else:
            # Create new user
            updates['_id'] = uid  # Ensure the document has the UID as its _id
            users_collection.insert_one(updates)
  
    def upload_generated_image_to_firebase_storage(self, image, uid):
        bucket = storage.bucket()
        unique_filename = str(uuid.uuid4())
        blob = bucket.blob(f'users/{uid}/dalle_images/{unique_filename}')
        file_data = image.read()
        blob.upload_from_string(file_data, content_type='image/jpeg')
        blob.make_public()
        
        return blob.public_url
    
    def delete_generated_image_from_firebase_storage(self, path):
        bucket = storage.bucket()
        blob = bucket.blob(path)
        blob.delete()

    def fetch_all_from_dalle_images(self, uid):
        bucket = storage.bucket()
        
        # Specify the folder path
        folder_path = f'users/{uid}/dalle_images/'
        
        # List all files in the folder
        blobs = bucket.list_blobs(prefix=folder_path)
        
        # Get the public url and blob name of each file
        images_list = [{'url': blob.public_url, 'path': blob.name} for blob in blobs]
        
        return images_list
    
    def upload_profile_image_to_firebase_storage(self, file, uid):
        bucket = storage.bucket()
        unique_filename = str(uuid.uuid4())
        blob = bucket.blob(f'users/{uid}/profile_images/{unique_filename}')
        file_data = file.read()
        blob.upload_from_string(file_data, content_type='image/jpeg')
        blob.make_public()

        # Update or insert the document with the given UID
        self.db['users'].update_one(
            {'_id': uid},  # Query matches the document with the given UID
            {'$set': {'avatar_url': blob.public_url}},  # Update operation
            upsert=True  # Create a new document if one doesn't exist
        )

        return blob.public_url
    
    def upload_file_to_firebase_storage(self, file, uid):
        bucket = storage.bucket()
        unique_filename = str(uuid.uuid4())
        blob = bucket.blob(f'users/{uid}/gpt-vision/{unique_filename}')
        file_data = file.read()
        blob.upload_from_string(file_data, content_type='image/jpeg')
        blob.make_public()

        return blob.public_url