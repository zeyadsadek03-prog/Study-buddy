import os
import uuid
import json
import sqlite3
import fitz
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('GROQ_API_KEY')
if not API_KEY:
    raise RuntimeError('Missing GROQ_API_KEY in environment')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())

DB_PATH = os.environ.get('DB_PATH', 'study_buddy.db')


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                token TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_text(text: str) -> str:
    token = uuid.uuid4().hex
    with get_db() as conn:
        conn.execute('INSERT INTO documents (token, text) VALUES (?, ?)', (token, text))
        conn.commit()
    return token


def load_text(token: str) -> str | None:
    with get_db() as conn:
        cur = conn.execute('SELECT text FROM documents WHERE token = ?', (token,))
        row = cur.fetchone()
    return row['text'] if row else None


def delete_text(token: str) -> None:
    with get_db() as conn:
        conn.execute('DELETE FROM documents WHERE token = ?', (token,))
        conn.commit()


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF allowed'}), 400

    if not os.path.exists('tmp'):
        os.makedirs('tmp', exist_ok=True)
    save_path = os.path.join('tmp', file.filename)
    file.save(save_path)

    try:
        doc = fitz.open(save_path)
        text = '\n'.join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({'error': f'PDF read failed: {str(e)}'}), 500
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)

    try:
        token = save_text(text[:8000])
        return jsonify({
            'filename': file.filename,
            'text': text[:4000] + ('...' if len(text) > 4000 else ''),
            'token': token,
            'ready': True,
        })
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


@app.route('/quiz', methods=['POST'])
def generate_quiz():
    data = request.json or {}
    token = data.get('token') or ''
    difficulty = (data.get('difficulty') or 'easy').lower()
    if difficulty not in {'easy', 'medium', 'hard'}:
        difficulty = 'easy'
    lens = (data.get('lens') or 'default').lower()
    if lens not in {'default', 'definitions', 'examples', 'exam'}:
        lens = 'default'

    text = load_text(token) if token else ''
    if not text:
        return jsonify({'error': 'No source text. Upload a PDF first.'}), 400

    base_prompt = (
        'You are a study quiz generator. Create 6 multiple-choice questions from the text below. '
        'For each question, provide 4 options and mark the correct answer. '
        'Return ONLY valid JSON like: '
        '[{"q":"...","options":["A","B","C","D"],"answer":"..."}]\\n\\n'
        f'TEXT:\n{text}'
    )

    difficulty_instructions = {
        'easy': 'Focus on direct recall and straightforward facts from the text.',
        'medium': 'Focus on interpretation and connecting ideas across the text.',
        'hard': 'Focus on inference, comparison, and deeper analysis beyond explicit statements.',
    }
    lens_instructions = {
        'default': '',
        'definitions': 'Prioritize key terms, acronyms, and conceptual definitions.',
        'examples': 'Prioritize applied scenarios, use cases, and concrete examples.',
        'exam': 'Mimic a university exam: include plausible distractors and avoid trivial questions.',
    }
    prompt = (
        base_prompt
        + '\n\nDifficulty: '
        + difficulty.upper()
        + '. '
        + difficulty_instructions.get(difficulty, difficulty_instructions['easy'])
        + '\nLens: '
        + lens.upper()
        + '. '
        + (lens_instructions.get(lens, '') or 'Keep questions balanced and directly based on the text.')
    )
    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        quiz = payload['choices'][0]['message']['content'].strip()
    except requests.HTTPError as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status == 429:
            return jsonify({'error': 'Too many requests — please wait a moment and try again.'}), 429
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500

    return jsonify({'quiz': quiz})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
