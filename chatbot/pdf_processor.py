import logging
import os
import pdfplumber
from docx import Document
from paddleocr import PaddleOCR

ocr_engine = None
gpt = None

def get_ocr_engine():
    """Thread-safe singleton retrieval for OCR engine"""
    global ocr_engine
    if ocr_engine is None:
        logger.info("Loading PaddleOCR model for the first time (this may take a few seconds)...")
        try:
            ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            logger.info("PaddleOCR loaded successfully.")
        except Exception as e:
            logger.error(f"PaddleOCR initialization failed: {e}", exc_info=True)
            raise RuntimeError("OCR engine initialization failed.")
    return ocr_engine

# Get logger for current module (assumes main program has configured logging)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts plain text content from a PDF or Word file.

    Args:
        file_path: Local path to the file

    Returns:
        Extracted full text string. Returns empty string if failed.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Local file does not exist: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise ValueError("File size is 0 bytes.")

    text_content = ""
    file_ext = os.path.splitext(file_path)[1].lower()
    logger.info(f"Starting to parse file: {file_path} (Type: {file_ext})")

    # --- 1. Handle Word Documents ---
    if file_ext in ['.docx', '.doc']:
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text_content += para.text + "\n"

            if not text_content.strip():
                logger.warning("No text extracted from Word document.")
                # Return empty text even if empty, let upper logic handle the prompt
                return ""

            logger.info(f"DOCX parsing successful, extracted {len(text_content)} characters.")
            return text_content

        except Exception as e:
            logger.error(f"DOCX parsing failed: {e}", exc_info=True)
            raise Exception(f"Word parsing failed: {str(e)}")

    # --- 2. Handle PDF Documents ---
    if file_ext == '.pdf':
        # 2.1 Attempt to extract text directly
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"

            # If text is sufficient, return directly
            if len(text_content.strip()) > 50:
                logger.info(f"PDF text extraction successful ({len(text_content)} characters).")
                return text_content

            logger.info(f"PDF text is sparse ({len(text_content)} characters), identified as scanned copy, starting OCR...")

        except Exception as e:
            logger.warning(f"pdfplumber extraction failed, attempting OCR: {e}")

        # 2.2 Start OCR
        try:
            local_ocr = get_ocr_engine()
            result = local_ocr.ocr(file_path, cls=True)

            ocr_text_list = []
            if result:
                for page_result in result:
                    if page_result:
                        for line in page_result:
                            if len(line) >= 2 and len(line[1]) >= 1:
                                ocr_text_list.append(line[1][0])

            ocr_text = "\n".join(ocr_text_list)

            if ocr_text and len(ocr_text.strip()) > 10:
                logger.info(f"✅ OCR recognition successful ({len(ocr_text)} characters).")
                return ocr_text
            else:
                logger.warning("OCR did not recognize valid text.")
                return ""

        except Exception as ocr_err:
            logger.error(f"OCR critical error: {ocr_err}", exc_info=True)
            raise Exception(f"OCR recognition failed: {str(ocr_err)}")

    raise ValueError(f"Unsupported file format: {file_ext}")


# Simple local test
if __name__ == "__main__":
    # Replace with your local test PDF path
    test_path = "test_resume.pdf"
    if os.path.exists(test_path):
        content = extract_text_from_pdf(test_path)
        print("--- Extracted Content Preview (First 500 chars) ---")
        print(content[:500])
    else:
        print("Test file not found, please modify test_path for debugging.")