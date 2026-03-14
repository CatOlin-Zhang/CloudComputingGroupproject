import os
import tempfile
import logging
import configparser
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from ChatGPT_HKBU import ChatGPT
from job_database import get_all_jobs_as_text
import pdfplumber
from docx import Document
from paddleocr import PaddleOCR

# ==========================================
# 配置与全局变量
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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


# ==========================================
# 核心业务逻辑 (被文本和文件共用)
# ==========================================
async def run_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, text_content: str):
    """
    核心分析函数：
    1. 接收文本内容 (无论是用户打的字，还是从文件提取的字)
    2. 调用 GPT 进行职位匹配
    3. 回复用户
    """
    if not text_content or len(text_content.strip()) == 0:
        await update.message.reply_text("未能提取到有效内容，请检查文件是否为空或纯图片。")
        return

    user_name = update.effective_user.first_name
    logger.info(f"开始为 {user_name} 分析内容，长度：{len(text_content)}")

    # 显示“正在思考”状态
    loading_message = await update.message.reply_text(' 正在分析简历并查询职位库...')

    try:
        # 1. 刷新职位数据 (确保是最新的)
        current_jobs = get_all_jobs_as_text()
        gpt.set_job_context(current_jobs)
        logger.info(f"AI 已加载 {len(current_jobs)} 字符的职位数据。")

        # 2. 提交给 GPT
        # 提示词优化：告诉 GPT 这是从文件提取的内容
        prompt = f"以下是用户上传的简历内容：\n\n{text_content}"
        response = gpt.submit(prompt)

        # 3. 回复结果
        await loading_message.edit_text(response)

    except Exception as e:
        logger.error(f"AI 分析过程中出错: {e}", exc_info=True)
        await loading_message.edit_text(f"分析出错：{str(e)}")


# ==========================================
# 消息处理器
# ==========================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户直接发送的文本消息"""
    user_text = update.message.text
    logger.info(f"USER TEXT: {user_text}")

    # 直接调用核心分析逻辑
    await run_analysis(update, context, user_text)


def extract_text_from_file_sync(file_path):
    """
    同步提取文本函数 (支持 PDF/DOCX + OCR)
    返回：提取到的文本字符串
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


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理文档：下载 -> 提取 -> 【传给核心逻辑】 -> 清理"""
    document = update.message.document
    file_name = document.file_name

    # 1. 格式预检
    if not file_name.lower().endswith(('.pdf', '.doc', '.docx')):
        await update.message.reply_text("⚠️ 仅支持 PDF 或 Word (.doc/.docx) 简历。")
        return

    loading_msg = await update.message.reply_text("📥 正在下载并解析文件...")
    file_path_local = None

    try:
        # 2. 获取下载链接
        file_obj = await document.get_file()
        file_url = file_obj.file_path

        if not file_url:
            raise Exception("无法获取文件下载链接。")

        # 3. 创建临时文件路径
        temp_dir = tempfile.gettempdir()
        _, ext = os.path.splitext(file_name)
        # 使用唯一文件名防止冲突
        file_path_local = os.path.join(temp_dir, f"resume_{update.effective_user.id}_{update.message.message_id}{ext}")

        logger.info(f"正在下载：{file_url} -> {file_path_local}")

        # 4. 异步下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            response.raise_for_status()
            with open(file_path_local, 'wb') as f:
                f.write(response.content)

        logger.info(f"✅ 下载成功：{file_path_local}")
        await loading_msg.edit_text("正在提取文本 (可能包含 OCR)...")

        # 5. 【关键步骤】提取文本
        extracted_text = extract_text_from_file_sync(file_path_local)

        if not extracted_text or len(extracted_text.strip()) == 0:
            await loading_msg.edit_text(
                "**解析失败**\n\n"
                "未能从文件中提取到任何文字。\n"
                "可能原因：\n"
                "1. 文件是纯图片且 OCR 无法识别\n"
                "2. 文件已加密\n"
                "3. 文件内容为空"
            )
            return

        # 6. 【核心连接】将提取的文本直接传给核心分析逻辑
        # 这里复用了 handle_text 的逻辑，用户体验一致
        await loading_msg.delete()  # 删除中间的“正在解析”消息，保持界面整洁
        await run_analysis(update, context, extracted_text)

    except Exception as e:
        logger.error(f"文档处理全流程出错：{e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        await loading_msg.edit_text(f"处理失败：{error_msg}")

    finally:
        # 7. 清理临时文件
        if file_path_local and os.path.exists(file_path_local):
            try:
                os.remove(file_path_local)
                logger.debug(f"临时文件已清理：{file_path_local}")
            except Exception as clean_err:
                logger.warning(f"删除临时文件失败：{clean_err}")


# ==========================================
# 主程序入口
# ==========================================
def main():
    logger.info('INIT: Loading configuration...')
    config = configparser.ConfigParser()
    # 确保 config.ini 在当前目录
    if not os.path.exists('config.ini'):
        logger.error("未找到 config.ini 文件！")
        return

    config.read('config.ini')

    global gpt
    gpt = ChatGPT(config)

    # 预加载职位数据
    job_data = get_all_jobs_as_text()
    gpt.set_job_context(job_data)
    logger.info(f"AI 初始化完成，已加载 {len(job_data)} 字符的职位数据。")

    logger.info('INIT: Connecting the Telegram bot...')
    app = ApplicationBuilder().token(config['TELEGRAM']['ACCESS_TOKEN']).build()

    logger.info('INIT: Registering handlers...')

    # 1. 处理文本消息
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 2. 处理文档消息 (简历)
    # 注意：filters.Document.ALL 会捕获所有文档，我们在函数内部做后缀名过滤
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info('✅ 机器人启动成功！正在监听消息...')
    app.run_polling()


if __name__ == '__main__':
    main()