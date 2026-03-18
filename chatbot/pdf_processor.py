import logging
import os
import pdfplumber
from docx import Document
from paddleocr import PaddleOCR
ocr_engine = None
gpt = None


def get_ocr_engine():
    """线程安全的 OCR 单例获取"""
    global ocr_engine
    if ocr_engine is None:
        logger.info("正在首次加载 PaddleOCR 模型 (这可能需要几秒钟)...")
        try:
            ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            logger.info("PaddleOCR 加载完成。")
        except Exception as e:
            logger.error(f"PaddleOCR 初始化失败: {e}", exc_info=True)
            raise RuntimeError("OCR 引擎初始化失败。")
    return ocr_engine
# 获取当前模块的 logger (假设主程序已配置 logging，若未配置则不会报错，只是不输出)
logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    从 PDF 文件中提取纯文本内容。

    参数:
        file_path: PDF 文件的本地路径

    返回:
        提取出的完整文本字符串。如果失败则返回空字符串。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"本地文件不存在：{file_path}")

    if os.path.getsize(file_path) == 0:
        raise ValueError("文件大小为 0 字节。")

    text_content = ""
    file_ext = os.path.splitext(file_path)[1].lower()
    logger.info(f"开始解析文件：{file_path} (类型：{file_ext})")

    # --- 1. 处理 Word 文档 ---
    if file_ext in ['.docx', '.doc']:
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text_content += para.text + "\n"

            if not text_content.strip():
                logger.warning("Word 文档未提取到文本。")
                # 即使是空文本也返回，让上层逻辑处理提示
                return ""

            logger.info(f"DOCX 解析成功，提取 {len(text_content)} 字符。")
            return text_content

        except Exception as e:
            logger.error(f"DOCX 解析失败: {e}", exc_info=True)
            raise Exception(f"Word 解析失败：{str(e)}")

    # --- 2. 处理 PDF 文档 ---
    if file_ext == '.pdf':
        # 2.1 尝试直接提取文字
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"

            # 如果文字足够多，直接返回
            if len(text_content.strip()) > 50:
                logger.info(f"PDF 文字提取成功 ({len(text_content)} 字符)。")
                return text_content

            logger.info(f"PDF 文字较少 ({len(text_content)} 字符)，判定为扫描件，启动 OCR...")

        except Exception as e:
            logger.warning(f"pdfplumber 提取失败，尝试 OCR: {e}")

        # 2.2 启动 OCR
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
                logger.info(f"✅ OCR 识别成功 ({len(ocr_text)} 字符)。")
                return ocr_text
            else:
                logger.warning("OCR 未识别到有效文字。")
                return ""

        except Exception as ocr_err:
            logger.error(f"OCR 严重错误: {ocr_err}", exc_info=True)
            raise Exception(f"OCR 识别失败：{str(ocr_err)}")

    raise ValueError(f"不支持的文件格式：{file_ext}")


# 简单的本地测试
if __name__ == "__main__":
    # 替换为你本地的测试 PDF 路径
    test_path = "test_resume.pdf"
    if os.path.exists(test_path):
        content = extract_text_from_pdf(test_path)
        print("--- 提取内容预览 (前500字) ---")
        print(content[:500])
    else:
        print("未找到测试文件，请修改 test_path 进行调试。")