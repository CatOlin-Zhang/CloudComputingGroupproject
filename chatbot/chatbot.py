# chatbot.py
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import logging
from config import load_secrets, BotConfig
from ChatGPT_HKBU import ChatGPT
from rag_engine import SimpleJobRAG
from pdf_processor import extract_text_from_pdf
import os
import tempfile # 用于临时保存上传的文件
import re


gpt = None
rag_engine = None



def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    logging.info('INIT: Loading configuration...')
    try:
        secrets = load_secrets()
    except FileNotFoundError as e:
        logging.error(e)
        return

    global gpt, rag_engine

    # 1. 初始化 LLM (不再需要传入 config 对象，类内部会自动加载)
    gpt = ChatGPT()

    # 2. 初始化 RAG 引擎 (使用 config 中的默认路径)
    try:
        rag_engine = SimpleJobRAG()
        logging.info("RAG Engine initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize RAG Engine: {e}")
        rag_engine = None

    logging.info('INIT: Connecting the Telegram bot...')
    app = ApplicationBuilder().token(secrets['TELEGRAM_TOKEN']).build()

    logging.info('INIT: Registering handlers...')

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logging.info('INIT: Initialization done! Start polling...')
    app.run_polling()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logging.info(f"USER TEXT: {user_text}")

    loading_message = await update.message.reply_text(BotConfig.LOADING_TEXT)

    relevant_jobs_context = ""

    if rag_engine:
        hits = rag_engine.search(user_text)
        if hits and "Not found" not in hits[0]:
            relevant_jobs_context = "\n\n---\n\n".join(hits)
            logging.info(f"RAG found {len(hits)} relevant jobs.")
        else:
            logging.info("RAG found no relevant jobs.")
            relevant_jobs_context = "No matching jobs found in database."
    else:
        relevant_jobs_context = "Job database not loaded."

    gpt.set_job_context(relevant_jobs_context)
    response = gpt.submit(user_text)

    await loading_message.edit_text(response)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户上传的 PDF 简历 (兼容旧版 python-telegram-bot)
    """
    doc = update.message.document
    file_name = doc.file_name
    user_id = update.message.from_user.id

    # 1. 基础校验
    if not file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ 抱歉，目前仅支持 PDF 格式的简历。")
        return

    logging.info(f"USER FILE: {file_name} (User ID: {user_id})")

    # 发送接收确认 (暂时不用 Markdown，防止文件名有特殊字符报错)
    reply_text = f"收到文件：{file_name}\n正在解析简历内容并匹配职位，请稍候..."
    loading_message = await update.message.reply_text(reply_text)

    # 2. 准备临时文件路径
    temp_filename = f"resume_{user_id}_{file_name}"
    local_path = os.path.join(os.getcwd(), temp_filename)

    try:
        # 获取文件对象
        file_obj = await context.bot.get_file(doc.file_id)

        # 【关键修改】兼容旧版下载方法
        # 尝试使用 download_to_custom (v13-v20 早期)，如果不行则用 download (v13 及更早)
        if hasattr(file_obj, 'download_to_custom'):
            await file_obj.download_to_custom(local_path)
        elif hasattr(file_obj, 'download'):
            # 旧版 download 方法通常直接接受路径字符串
            await file_obj.download(custom_path=local_path)
        else:
            # 极老版本的回退方案
            await file_obj.download_to_drive(local_path) if hasattr(file_obj, 'download_to_drive') else None

        # 再次检查文件是否真的生成了
        if not os.path.exists(local_path):
            # 如果上述方法都没生成文件，尝试最原始的 download (无参数，保存到当前目录)
            # 注意：这可能会保存为 file_id 命名的文件，需要重命名，这里先尝试带参数的
            raise FileNotFoundError("Download method failed to create file.")

        logging.info(f"File downloaded successfully to: {local_path}")

        # 3. 提取文本
        resume_text = extract_text_from_pdf(local_path)

        if not resume_text or len(resume_text.strip()) < 50:
            await loading_message.edit_text(
                "解析失败\n\n无法从该 PDF 中提取有效文本。\n"
                "可能原因：文件是扫描件/图片或已加密。\n"
                "建议：请直接复制简历中的【技能】和【工作经验】文字发送给我。"
            )
            return

        logging.info(f"PDF parsed successfully. Length: {len(resume_text)} chars.")

        # 4. 调用 RAG 引擎
        if rag_engine:
            await loading_message.edit_text("简历解析完成，正在数据库中为您匹配最佳职位...")

            query_text = resume_text[:2000]
            hits = rag_engine.search(query_text)

            if hits and "未找到" not in hits[0]:
                response_msg = f"匹配成功！根据您的简历，为您推荐以下 {len(hits)} 个职位：\n\n"

                for i, job in enumerate(hits, 1):
                    # 清理 job 字符串中的换行符，防止格式混乱
                    clean_job = str(job).replace('\n', ' ')
                    response_msg += f"{i}. {clean_job}\n\n"

                response_msg += " 您可以告诉我您想深入了解哪一个。"
                await loading_message.edit_text(response_msg)
            else:
                await loading_message.edit_text(
                    "暂无完全匹配的职位\n\n"
                    "数据库中没有找到与您简历高度匹配的岗位。\n"
                    "建议：您可以尝试直接发送您想从事的职位名称或核心技能（例如：'Python 开发'）。"
                )
        else:
            await loading_message.edit_text("职位数据库未加载，暂时无法进行推荐。")

    except Exception as e:
        error_msg = str(e).replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
        logging.exception(f"Error processing document {file_name}: {error_msg}")

        await loading_message.edit_text(
            f"处理出错\n\n在解析文件时发生异常：{error_msg}\n"
            "请稍后重试，或直接发送文字描述您的需求。"
        )

    finally:
        # 5. 清理临时文件
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
                logging.debug(f"Temp file cleaned: {local_path}")
            except OSError:
                pass

if __name__ == '__main__':
    main()