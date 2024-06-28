import os
import random
import string

# Function to generate a random API key
def generate_api_key(length=32):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Generate a new API key
new_api_key = generate_api_key()

# Path to the .env file
env_file_path = '.env'

# Read the existing .env file
if os.path.exists(env_file_path):
    with open(env_file_path, 'r') as file:
        lines = file.readlines()

    # Replace the existing API key with the new one
    with open(env_file_path, 'w') as file:
        for line in lines:
            if line.startswith('REACT_APP_API_KEY='):
                file.write(f'REACT_APP_API_KEY={new_api_key}\n')
            else:
                file.write(line)
else:
    # If the .env file does not exist, create it and add the new API key
    with open(env_file_path, 'w') as file:
        file.write(f'REACT_APP_API_KEY={new_api_key}\n')

print(f'New API key generated and saved to .env file: {new_api_key}')