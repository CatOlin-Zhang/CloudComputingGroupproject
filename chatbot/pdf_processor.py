import logging
from pypdf import PdfReader
import os

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
    try:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return ""

        logger.info(f"开始解析 PDF: {os.path.basename(file_path)}")

        reader = PdfReader(file_path)
        text_content = []

        # 遍历每一页提取文本
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)

        full_text = "\n".join(text_content)

        if not full_text.strip():
            logger.warning(f"PDF 解析结果为空，可能是扫描版图片或加密文件: {file_path}")
            return ""

        logger.info(f"PDF 解析成功，提取字符数: {len(full_text)}")
        return full_text

    except Exception as e:
        logger.exception(f"解析 PDF 时发生严重错误: {e}")
        return ""


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