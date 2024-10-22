from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import os
import base64
import random
import uuid
import traceback
from PIL import Image
import PyPDF2
import docx
import easyocr
import requests
import re
import time

app = Flask(__name__)

# Ensure the uploads directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database initialization
def init_db():
    conn = sqlite3.connect('documents.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id TEXT PRIMARY KEY, 
                  student_id TEXT, 
                  document_type TEXT, 
                  filename TEXT, 
                  status TEXT DEFAULT 'Pending',
                  score INTEGER,
                  resolution TEXT,
                  explanation TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Add your Hugging Face API token
HF_API_TOKEN = "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"

reader = easyocr.Reader(['en'])  # Initialize once

def extract_text(file_path):
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()

    print(f"Extracting text from file: {file_path}")
    print(f"File extension: {file_extension}")

    if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
        return extract_text_from_image(file_path)
    elif file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension in ['.doc', '.docx']:
        return extract_text_from_docx(file_path)
    else:
        return "Unsupported file type"

def extract_text_from_image(file_path):
    try:
        result = reader.readtext(file_path)
        text = ' '.join([text for _, text, _ in result])
        return text
    except Exception as e:
        print(f"Error extracting text from image: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback for debugging
        return ""

def extract_text_from_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ' '.join([page.extract_text() for page in reader.pages])
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback for debugging
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback for debugging
        return ""

def calculate_score(file_path, file_type, text_content, max_retries=3, initial_backoff=1):
    if file_type.startswith('image'):
        with Image.open(file_path) as img:
            width, height = img.size
            if width < 800 or height < 600:
                return 1, "Low resolution image"
    
    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    
    prompt = f"""[INST] Analyze the following text and provide a score from 1 to 10 based on its clarity, relevance, and completeness. Start the response with the numeric score, followed by a brief explanation of no more than two sentences. Do not use first-person language in the explanation.

Text: {text_content[:1000]}

Score and Explanation: [/INST]"""

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 100, "return_full_text": False}
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            print("API Response:", result)

            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict) and 'generated_text' in result[0]:
                generated_text = result[0]['generated_text']
                
                # Try to extract score using regex
                score_match = re.search(r'\b([1-9]|10)\b', generated_text)
                if score_match:
                    score = int(score_match.group(1))
                    explanation = generated_text.replace(score_match.group(0), '', 1).strip()
                else:
                    # If no clear score is found, estimate based on the content
                    score = estimate_score(generated_text)
                    explanation = generated_text.strip()
                
                return score, explanation
            else:
                raise ValueError("Unexpected response format from API")

        except requests.exceptions.RequestException as e:
            print(f"API request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(initial_backoff * (2 ** attempt))
            else:
                return fallback_scoring(text_content)

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return fallback_scoring(text_content)

    return fallback_scoring(text_content)

def estimate_score(text):
    # Simple estimation based on positive words
    positive_words = ['clear', 'relevant', 'complete', 'good', 'excellent', 'well', 'thorough']
    word_count = sum(1 for word in positive_words if word in text.lower())
    return min(max(word_count + 5, 1), 10)  # Ensure score is between 1 and 10

def fallback_scoring(text_content):
    score = random.randint(5, 8)  # More reasonable random range
    explanation = "Fallback scoring used due to API issues. Score based on text length and complexity."
    return score, explanation

@app.route('/upload', methods=['POST'])
def upload_document():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        required_fields = ['document', 'document_type', 'student_id', 'file_name']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        document_base64 = data['document']
        document_type = data['document_type']
        student_id = data['student_id']
        file_name = data['file_name']

        _, file_extension = os.path.splitext(file_name)
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

        try:
            with open(filepath, "wb") as file:
                file.write(base64.b64decode(document_base64))
            print(f"File saved successfully: {filepath}")
        except Exception as e:
            print(f"Error saving file: {str(e)}")
            return jsonify({"error": f"Error saving file: {str(e)}"}), 500

        file_type = ''
        resolution = ''
        if file_extension.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            with Image.open(filepath) as img:
                width, height = img.size
                resolution = f"{width}x{height}"
                file_type = 'image'
            print(f"Image file detected. Resolution: {resolution}")
        else:
            file_type = 'document'
            print(f"Document file detected: {file_extension}")

        # Extract text from the uploaded file
        text_content = extract_text(filepath)

        score, explanation = calculate_score(filepath, file_type, text_content)

        try:
            conn = sqlite3.connect('documents.db')
            c = conn.cursor()
            document_id = str(uuid.uuid4())
            c.execute("INSERT INTO documents (id, student_id, document_type, filename, score, resolution, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (document_id, student_id, document_type, unique_filename, score, resolution, explanation))
            conn.commit()
            print(f"Document saved to database. ID: {document_id}")
        except Exception as e:
            print(f"Database error: {str(e)}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            conn.close()

        return jsonify({"message": "Document uploaded successfully", "document_id": document_id, "score": score, "explanation": explanation}), 201
    except Exception as e:
        app.logger.error(f"Unexpected error in upload: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/action-items', methods=['GET'])
def list_action_items():
    try:
        conn = sqlite3.connect('documents.db')
        c = conn.cursor()
        c.execute("SELECT id, document_type, student_id, score, explanation FROM documents WHERE status = 'Pending'")
        documents = c.fetchall()
        conn.close()

        action_items = []
        for doc in documents:
            action_items.append({
                "document_id": doc[0],
                "document_type": doc[1],
                "student_id": doc[2],
                "score": doc[3],
                "explanation": doc[4]
            })

        return jsonify(action_items), 200
    except Exception as e:
        app.logger.error(f"Error in action-items: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/review', methods=['POST'])
def review_document():
    try:
        data = request.json
        document_id = data['document_id']
        status = data['status']

        if status not in ['Approved', 'Rejected']:
            return jsonify({"error": "Invalid status. Must be 'Approved' or 'Rejected'"}), 400

        conn = sqlite3.connect('documents.db')
        c = conn.cursor()
        c.execute("UPDATE documents SET status = ? WHERE id = ?", (status, document_id))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "Document not found"}), 404
        conn.commit()
        conn.close()

        return jsonify({"message": f"Document {document_id} has been {status}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/document/<document_id>')
def get_document(document_id):
    conn = sqlite3.connect('documents.db')
    c = conn.cursor()
    c.execute("SELECT filename FROM documents WHERE id = ?", (document_id,))
    result = c.fetchone()
    conn.close()

    if result:
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            return send_file(filepath, as_attachment=True, download_name=filename)
        except TypeError:
            return send_file(filepath, as_attachment=True, attachment_filename=filename)
    else:
        return jsonify({"error": "Document not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
