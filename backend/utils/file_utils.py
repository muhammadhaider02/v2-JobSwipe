import PyPDF2
from docx import Document
import os

def extract_text_from_pdf(filepath):
    """
    Extract text from a PDF file
    """
    text = ""
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")
    
    return text.strip()

def extract_text_from_docx(filepath):
    """
    Extract text from a DOCX file
    """
    text = ""
    try:
        doc = Document(filepath)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        raise Exception(f"Error reading DOCX: {str(e)}")
    
    return text.strip()

def extract_text_from_file(filepath):
    """
    Extract text from PDF or DOCX file based on extension
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    file_extension = os.path.splitext(filepath)[1].lower()
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(filepath)
    elif file_extension in ['.docx', '.doc']:
        return extract_text_from_docx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
