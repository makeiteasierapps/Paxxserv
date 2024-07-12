from .OpenAiClientBase import OpenAiClientBase

class ImageManager(OpenAiClientBase):    
    def generate_image(self, request):
            prompt = request['prompt']
            size=request['size'].lower()
            quality=request['quality'].lower()
            style=request['style'].lower()
            

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                quality=quality,
                style=style,
            )

            return response.data[0].url