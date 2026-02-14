to run:
uvicorn app.main:app --reload --port 8000

env file:

DB_NAME=mutual_aid

MONGO_URI=mongodb+srv://USERNAME:PASSWORD@cluster0.so1kl0s.mongodb.net/mutual_aid?retryWrites=true&w=majority&appName=Cluster0

GEMINI_API_KEY=REDACTED

GEMINI_MODEL=gemini-2.5-flash