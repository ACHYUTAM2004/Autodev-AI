from google import genai
import os

api_key="AIzaSyBh-I3l0G7Hx-qTZWjRnqZX4cGXfWor8_0"
client = genai.Client(api_key=api_key)

try:
    print("⏳ Testing Gemini 2.5 Flash...")
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents="Are you ready to write code?"
    )
    print(f"✅ Success! Response: {response.text}")

except Exception as e:
    print(f"❌ Failed: {e}")