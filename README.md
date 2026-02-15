# RescueRun
AI-assisted mutual aid app for posting urgent needs, community funding, and helper delivery.

## Details
**What problem does this project solve?**  
RescueRun helps with local coordination during emergencies when people need medicine, food, shelter, or transport quickly. It converts messy text requests into structured tasks, prioritizes urgent ones, and lets the community fund and deliver help.

**Did you use any interesting libraries or services?**  
- FastAPI for backend APIs  
- MongoDB Atlas + PyMongo for persistence  
- Google Gemini API for AI intake parsing (with heuristic fallback)  
- React + Vite frontend  
- Leaflet / react-leaflet for map UX  
- Framer Motion + Tailwind CSS for interactive UI
- Rule-based triage scoring for prioritization

**What extension type(s) did you build?**  
Web app with:
- AI intake extension (`/v1/ai/invoke`) to structure requests from messy text  
- Ranking/triage extension (`/v1/ai/rank`) to prioritize requests by urgency, severity, and funding gap  
- Map-based coordination extension for donors and helpers
- Crisis-mode prioritization in frontend to surface only high-priority actionable tasks

**If given longer, what would be the next improvement you would make?**  
Add stronger trust and operations features: better ranking models, anti-fraud checks, helper ETA/routing, and offline-friendly support.

## Set Up Instructions
### 1. Prerequisites
- Python 3.10+  
- Node.js 20+  
- MongoDB Atlas database  
- Gemini API key (optional, but recommended)

### 2. Backend setup
From project root:

```bash
pip install -r requirements.txt
```

Create `.env` in project root:

```env
DB_NAME=mutual_aid
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.so1kl0s.mongodb.net/mutual_aid?retryWrites=true&w=majority&appName=Cluster0
GEMINI_API_KEY=<your_gemini_key>
GEMINI_MODEL=gemini-2.5-flash
```

Run backend:

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend setup
From project root:

```bash
cd frontend
npm install
npm run dev
```

Open:
- Frontend: `http://localhost:5173`  
- Backend API: `http://localhost:8000`

### 4. Third-party registrations
- MongoDB Atlas account + cluster + DB user  
- Google AI Studio / Gemini API key

## Screenshots
TBD

## Collaborators
- [Vaibhav Thalanki](https://github.com/Vaibhav-Thalanki)
- [Ackshay N R](https://github.com/Ackshay206)
- [Vinaya Rekha](https://github.com/avr5317)

