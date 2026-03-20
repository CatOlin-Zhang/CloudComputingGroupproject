import logging
from pypdf import PdfReader
import os

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract plain text content from a PDF file.


    file_path: Local path of the PDF file

    The complete extracted text string. Returns an empty string if it fails.
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return ""

        logger.info(f"Start parsing PDF: {os.path.basename(file_path)}")

        reader = PdfReader(file_path)
        text_content = []

        # Traverse each page to extract text
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)

        full_text = "\n".join(text_content)

        if not full_text.strip():
            logger.warning(f"The PDF parsing result is empty, possibly because it is a scanned image or an encrypted file.: {file_path}")
            return ""

        logger.info(f"PDF parsing successful, number of characters extracted: {len(full_text)}")
        return full_text

    except Exception as e:
        logger.exception(f"A serious error occurred while parsing the PDF: {e}")
        return ""


# local test
if __name__ == "__main__":
    test_path = "test_resume.pdf"
    if os.path.exists(test_path):
        content = extract_text_from_pdf(test_path)
        print("--- Content Extraction Preview (First 500 Characters) ---")
        print(content[:500])
    else:
        print("Test file not found, please modify test_path for debugging.")