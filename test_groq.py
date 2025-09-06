import os
from groq import Groq
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Grab API key
api_key = os.getenv("GROQ_API_KEY")
print("API key loaded:", api_key[:8] + "..." if api_key else "None")

# Initialize client
client = Groq(api_key=api_key)

try:
    # Simple test call
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": "Hello Groq, say hi in one line"}],
        model="llama-3.1-8b-instant"
    )

    print("Response:", chat_completion.choices[0].message.content)

except Exception as e:
    print("Error calling Groq:", e)
