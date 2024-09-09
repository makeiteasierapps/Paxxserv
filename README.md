
## Obtain API Keys
- **[GNews API Key](https://gnews.io/)**
- **[OpenAI API Key](https://openai.com/product)** 
**Note:** OpenAI requires a paid account for API access to GPT-4 models.


## Setup MongoDB
- **[Create a free account](https://www.mongodb.com/)** 
- **[Deploy a free tier Cluster](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/)**
- **[Get your URI](https://www.mongodb.com/docs/atlas/tutorial/connect-to-your-cluster/#connect-to-your-atlas-cluster)**
    - Steps 1-6 only
    - Replace MONGO_URI in the .env with the string you got from the above steps.


## Environment Variables 
- OPENAI_API_KEY
- GNEWS_API_KEY
- MONGO_URI = 'mongodb+srv://yourUsername:yourPassword@yourAppName.y7fnlbg.mongodb.net/?retryWrites=true&w=majority&appName=yourAppName'
- FIREBASE_ADMIN_SDK = 'app/fb_config/your-firebase-config.json'
- FIREBASE_API_KEY
- FIREBASE_AUTH_DOMAIN
- FIREBASE_PROJECT_ID
- FIREBASE_MESSAGING_SENDER_ID
- FIREBASE_APP_ID

## Additional Steps
- Create a virtual env and install requirements.txt(run the following commands from the root of the project)
    - `python -m venv venv`
    - `. venv/bin/activate`
    - `pip install -r requirements.txt`
- Create a fb_config folder inside of the app folder and add the values from step 3 of the Paxxium Firebase Setup.
- Start the server
    - `hypercorn run:app --worker-class asyncio --bind 0.0.0.0:3033 --debug --reload`