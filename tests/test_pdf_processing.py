import pytest
import requests
from app import extract_text_from_pdf, generate_summary

def test_openai_guide_processing():
    """Test processing of the OpenAI guide PDF."""
    # Download the PDF
    pdf_url = "https://www.learningcontainer.com/wp-content/uploads/2019/09/sample-pdf-file.pdf"
    response = requests.get(pdf_url)
    assert response.status_code == 200, "Failed to download test PDF"
    
    # Extract text
    pdf_text = extract_text_from_pdf(response.content)
    assert len(pdf_text) > 0, "No text extracted from PDF"
    
    # Check for key terms that should be in the document
    key_terms = [
        "agent",
        "openai",
        "building",
        "practical",
        "guide"
    ]
    for term in key_terms:
        assert term.lower() in pdf_text.lower(), f"Key term '{term}' not found in extracted text"
    
    # Test summary generation
    summary = generate_summary(pdf_text)
    assert len(summary) > 0, "No summary generated"
    assert len(summary) < len(pdf_text), "Summary should be shorter than original text"
    
    # Check if summary contains key concepts
    summary_key_terms = [
        "agent",
        "guide",
        "building",
        "practical"
    ]
    for term in summary_key_terms:
        assert term.lower() in summary.lower(), f"Key term '{term}' not found in summary"

def test_pdf_processing_with_mock_data():
    """Test PDF processing with mock data without Slack API calls."""
    # Mock PDF content (you can replace this with actual PDF content for testing)
    mock_pdf_content = b"%PDF-1.4\n%Test PDF content"
    
    # Test text extraction
    pdf_text = extract_text_from_pdf(mock_pdf_content)
    assert isinstance(pdf_text, str), "Text extraction should return a string"
    
    # Test summary generation
    summary = generate_summary(pdf_text)
    assert isinstance(summary, str), "Summary should be a string"
    assert len(summary) > 0, "Summary should not be empty" 