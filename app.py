from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import PyPDF2
import os
import sqlite3
import requests
import json
from datetime import datetime
import cohere
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Cohere client (updated for Chat API)
try:
    co = cohere.ClientV2(api_key=os.getenv('COHERE_API_KEY', 'your-cohere-api-key-here'))
    print("Cohere client initialized successfully")
except Exception as e:
    print(f"Error initializing Cohere client: {e}")
    co = None

# Database initialization
def init_db():
    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT,
            abstract TEXT,
            content TEXT,
            summary TEXT,
            research_gaps TEXT,
            methodology TEXT,
            key_findings TEXT,
            filename TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF file"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error extracting text: {e}")
    return text

def get_cohere_summary(text):
    """Generate summary using Cohere Chat API"""
    if co is None:
        return "AI Summary: [Cohere API key not configured. Please add a valid API key to enable AI analysis.]"
    
    try:
        # Truncate text if too long (Cohere has token limits)
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        response = co.chat(
            model='command-a-03-2025',
            messages=[
                {
                    "role": "system", 
                    "content": "You are an AI assistant that summarizes academic research papers. Provide concise, accurate summaries that capture the main contributions, methodology, and findings."
                },
                {
                    "role": "user", 
                    "content": f"Please summarize the following research paper:\n\n{text}"
                }
            ]
        )
        
        return response.message.content[0].text
    except Exception as e:
        print(f"Error generating summary: {e}")
        return f"Error generating summary: {str(e)}"

def analyze_research_gaps(text):
    """Analyze research gaps using Cohere Chat API"""
    if co is None:
        return "Research Gap Analysis: [Cohere API key not configured. Please add a valid API key to enable AI analysis.]"
    
    try:
        if len(text) > 6000:
            text = text[:6000] + "..."
        
        response = co.chat(
            model='command-a-03-2025',
            messages=[
                {
                    "role": "system", 
                    "content": "You are a research analyst specializing in identifying research gaps and future work opportunities in academic papers. Provide structured analysis focusing on limitations, gaps, and future research directions."
                },
                {
                    "role": "user", 
                    "content": f"""Analyze the following research paper text and identify:
1. Key limitations in the current research
2. Potential research gaps
3. Future work opportunities
4. Unexplored areas

Text: {text}

Please provide a structured analysis focusing on research gaps and future opportunities."""
                }
            ]
        )
        
        return response.message.content[0].text
    except Exception as e:
        print(f"Error analyzing research gaps: {e}")
        return f"Error analyzing research gaps: {str(e)}"

def extract_key_findings(text):
    """Extract key findings and methodology using Cohere Chat API"""
    if co is None:
        return "Key Findings: [Cohere API key not configured. Please add a valid API key to enable AI analysis.]"
    
    try:
        if len(text) > 6000:
            text = text[:6000] + "..."
        
        response = co.chat(
            model='command-a-03-2025',
            messages=[
                {
                    "role": "system", 
                    "content": "You are a research analyst that extracts key findings, methodology, and contributions from academic papers. Provide clear, structured summaries of research elements."
                },
                {
                    "role": "user", 
                    "content": f"""Extract from this research paper:
1. Key findings and main contributions
2. Research methodology used
3. Results and conclusions

Text: {text}

Provide a concise summary of these elements."""
                }
            ]
        )
        
        return response.message.content[0].text
    except Exception as e:
        print(f"Error extracting key findings: {e}")
        return f"Error extracting key findings: {str(e)}"

# ... rest of the code remains the same ...

@app.route('/')
def index():
    """Main page showing all uploaded papers"""
    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM papers ORDER BY upload_date DESC')
    papers = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries for easier template handling
    papers_list = []
    for paper in papers:
        papers_list.append({
            'id': paper[0],
            'title': paper[1],
            'authors': paper[2],
            'abstract': paper[3],
            'summary': paper[5],
            'research_gaps': paper[6],
            'upload_date': paper[10]
        })
    
    return render_template('index.html', papers=papers_list)

@app.route('/upload', methods=['GET', 'POST'])
def upload_paper():
    """Handle paper upload and processing"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extract text from PDF
            content = extract_text_from_pdf(filepath)
            if not content.strip():
                flash('Could not extract text from PDF')
                return redirect(request.url)
            
            # Extract basic metadata (simple approach)
            lines = content.split('\n')
            title = lines[0] if lines else "Unknown Title"
            authors = lines[1] if len(lines) > 1 else "Unknown Authors"
            abstract = lines[2] if len(lines) > 2 else "No abstract found"
            
            # Generate AI analysis
            summary = get_cohere_summary(content)
            research_gaps = analyze_research_gaps(content)
            key_findings = extract_key_findings(content)
            
            # Save to database
            conn = sqlite3.connect('papers.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO papers (title, authors, abstract, content, summary, research_gaps, methodology, key_findings, filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, authors, abstract, content, summary, research_gaps, "Methodology extracted", key_findings, filename))
            conn.commit()
            conn.close()
            
            # Clean up uploaded file
            os.remove(filepath)
            
            flash('Paper uploaded and analyzed successfully!')
            return redirect(url_for('index'))
        else:
            flash('Please upload a PDF file')
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/paper/<int:paper_id>')
def view_paper(paper_id):
    """View detailed analysis of a specific paper"""
    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM papers WHERE id = ?', (paper_id,))
    paper = cursor.fetchone()
    conn.close()
    
    if not paper:
        flash('Paper not found')
        return redirect(url_for('index'))
    
    paper_data = {
        'id': paper[0],
        'title': paper[1],
        'authors': paper[2],
        'abstract': paper[3],
        'content': paper[4],
        'summary': paper[5],
        'research_gaps': paper[6],
        'methodology': paper[7],
        'key_findings': paper[8],
        'filename': paper[9],
        'upload_date': paper[10]
    }
    
    return render_template('paper_detail.html', paper=paper_data)

@app.route('/search')
def search_papers():
    """Search papers by keywords"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, authors, abstract, summary FROM papers 
        WHERE title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR summary LIKE ?
        ORDER BY upload_date DESC
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
    results = cursor.fetchall()
    conn.close()
    
    papers = []
    for result in results:
        papers.append({
            'id': result[0],
            'title': result[1],
            'authors': result[2],
            'abstract': result[3],
            'summary': result[4]
        })
    
    return jsonify(papers)

@app.route('/api/papers')
def api_papers():
    """API endpoint to get all papers"""
    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, authors, abstract, summary, upload_date FROM papers ORDER BY upload_date DESC')
    papers = cursor.fetchall()
    conn.close()
    
    papers_list = []
    for paper in papers:
        papers_list.append({
            'id': paper[0],
            'title': paper[1],
            'authors': paper[2],
            'abstract': paper[3],
            'summary': paper[4],
            'upload_date': paper[5]
        })
    
    return jsonify(papers_list)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)