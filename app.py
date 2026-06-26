import os
import fitz  # PyMuPDF
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF allowed"}), 400

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(save_path)

    text = ""
    try:
        doc = fitz.open(save_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        return jsonify({"error": f"PDF read failed: {str(e)}"}), 500
    finally:
        # Cleanup uploaded PDF
        if os.path.exists(save_path):
            os.remove(save_path)

    return jsonify({
        "filename": file.filename,
        "pages": len(text),
        "text": text[:4000] + ("..." if len(text) > 4000 else "")
    })

@app.route('/quiz', methods=['POST'])
def generate_quiz():
    # Placeholder for quiz generation — we'll implement after upload works
    return jsonify({"message": "Quiz generation endpoint ready"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
