import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
REDIS_URL = os.getenv("REDIS_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
