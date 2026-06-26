from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    # Placeholder — we'll implement this after setting up AI + PDF/transcript
    return jsonify({"message": "Upload endpoint ready"})

@app.route('/quiz', methods=['POST'])
def generate_quiz():
    # Placeholder for quiz generation
    return jsonify({"message": "Quiz generation endpoint ready"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
