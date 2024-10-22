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
                  resolution TEXT)''')
    conn.commit()
    conn.close()

init_db()

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

def calculate_score(file_path, file_type, text_content):
    if file_type.startswith('image'):
        with Image.open(file_path) as img:
            width, height = img.size
            if width < 800 or height < 600:
                return 1
    
    # Print the extracted text content
    print(f"Extracted text content from {file_path}:")
    print(text_content[:500])  # Print first 500 characters
    print("=" * 50)  # Separator for readability in console output

    # For now, we'll still return a random score
    return random.randint(2, 10)

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

        score = calculate_score(filepath, file_type, text_content)

        try:
            conn = sqlite3.connect('documents.db')
            c = conn.cursor()
            document_id = str(uuid.uuid4())
            c.execute("INSERT INTO documents (id, student_id, document_type, filename, score, resolution) VALUES (?, ?, ?, ?, ?, ?)",
                      (document_id, student_id, document_type, unique_filename, score, resolution))
            conn.commit()
            print(f"Document saved to database. ID: {document_id}")
        except Exception as e:
            print(f"Database error: {str(e)}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        finally:
            conn.close()

        return jsonify({"message": "Document uploaded successfully", "document_id": document_id, "score": score}), 201
    except Exception as e:
        app.logger.error(f"Unexpected error in upload: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/action-items', methods=['GET'])
def list_action_items():
    try:
        conn = sqlite3.connect('documents.db')
        c = conn.cursor()
        c.execute("SELECT id, document_type, student_id, score FROM documents WHERE status = 'Pending'")
        documents = c.fetchall()
        conn.close()

        action_items = []
        for doc in documents:
            action_items.append({
                "document_id": doc[0],
                "document_type": doc[1],
                "student_id": doc[2],
                "score": doc[3]
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
