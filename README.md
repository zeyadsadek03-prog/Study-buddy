# Study Buddy
Upload a PDF and generate AI-powered study quizzes.

## Live
https://study-buddy-psi-tan.vercel.app/

## Run locally
1. Copy `.env.example` to `.env` and set `GROQ_API_KEY`
2. `pip install -r requirements.txt`
3. `python app.py`

## Deploy to Vercel
- Import this repo into Vercel.
- Set `GROQ_API_KEY` in Vercel environment variables.
- Enable Vercel KV in your Vercel dashboard. Vercel will add `KV_REST_API_URL` and `KV_REST_API_TOKEN` automatically.
- Redeploy.
