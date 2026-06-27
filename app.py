import os
import fitz  # PyMuPDF
import yt_dlp
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
API_KEY=os.getenv('GOOGLE_API_KEY')
if not API_KEY:
    raise RuntimeError('Missing GOOGLE_API_KEY in environment')

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

client = genai.Client(api_key=API_KEY)

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

    session['source_text'] = text[:8000]
    return jsonify({
        'filename': file.filename,
        'text': text[:4000] + ('...' if len(text) > 4000 else ''),
        'ready': True,
    })


@app.route('/url', methods=['POST'])
def url_input():
    data = request.json or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    text = ''
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'tr', 'ar'],
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts['outtmpl'] = os.path.join(tmpdir, '%(title)s.%(ext)s')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subs = info.get('automatic_captions') or info.get('subtitles') or {}
                sub_url = None
                for lang in ['en', 'tr', 'ar']:
                    if lang in subs:
                        for fmt in subs[lang]:
                            if fmt.get('ext') == 'vtt':
                                sub_url = fmt.get('url')
                                break
                        if sub_url:
                            break
                if sub_url:
                    import requests
                    r = requests.get(sub_url, timeout=20)
                    text = r.text or ''
    except Exception as e:
        return jsonify({'error': f'URL fetch failed: {str(e)}'}), 500

    session['source_text'] = text[:8000]
    return jsonify({'text': text[:4000] + ('...' if len(text) > 4000 else text), 'ready': True})


@app.route('/quiz', methods=['POST'])
def generate_quiz():
    data = request.json or {}
    text = session.get('source_text') or data.get('text') or ''
    if not text:
        return jsonify({'error': 'No source text. Upload a PDF or paste a URL first.'}), 400

    prompt = (
        'You are a study quiz generator. Create 6 multiple-choice questions from the text below. '
        'For each question, provide 4 options and mark the correct answer. '
        'Return JSON like: '
        '[{"q":"...","options":["A","B","C","D"],"answer":"..."}]\n\n'
        f'TEXT:\n{text}'
    )
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        quiz = response.text or '[]'
    except Exception as e:
        return jsonify({'error': f'AI generation failed: {str(e)}'}), 500

    return jsonify({'quiz': quiz})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
