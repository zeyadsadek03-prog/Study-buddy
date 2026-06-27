import os
import uuid
import json
import fitz  # PyMuPDF
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('GROQ_API_KEY')
if not API_KEY:
    raise RuntimeError('Missing GROQ_API_KEY in environment')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

STORE_DIR = 'text_store'
os.makedirs(STORE_DIR, exist_ok=True)


def save_text(text: str) -> str:
    token = uuid.uuid4().hex
    path = os.path.join(STORE_DIR, f'{token}.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return token


def load_text(token: str) -> str | None:
    path = os.path.join(STORE_DIR, f'{token}.txt')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def delete_text(token: str) -> None:
    path = os.path.join(STORE_DIR, f'{token}.txt')
    if os.path.exists(path):
        os.remove(path)


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

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(save_path)

    try:
        doc = fitz.open(save_path)
        text = '\n'.join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        return jsonify({'error': f'PDF read failed: {str(e)}'}), 500
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)

    token = save_text(text[:8000])
    return jsonify({
        'filename': file.filename,
        'text': text[:4000] + ('...' if len(text) > 4000 else ''),
        'token': token,
        'ready': True,
    })


@app.route('/quiz', methods=['POST'])
def generate_quiz():
    data = request.json or {}
    token = data.get('token') or ''
    text = load_text(token) if token else ''
    if not text:
        return jsonify({'error': 'No source text. Upload a PDF first.'}), 400

    prompt = (
        'You are a study quiz generator. Create 6 multiple-choice questions from the text below. '
        'For each question, provide 4 options and mark the correct answer. '
        'Return ONLY valid JSON like: '
        '[{"q":"...","options":["A","B","C","D"],"answer":"..."}]\n\n'
        f'TEXT:\n{text}'
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
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500

    delete_text(token)
    return jsonify({'quiz': quiz})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
