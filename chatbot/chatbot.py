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

import httpx
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
        if hits and "未找到" not in hits[0]:
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

    # 1. 格式预检
    if not file_name.lower().endswith(('.pdf', '.doc', '.docx')):
        await update.message.reply_text(" 仅支持 PDF 或 Word (.doc/.docx) 简历。")
        return

    loading_message = await update.message.reply_text("📥 正在下载并解析文件...")
    local_path = None
    try:
        # 2. 获取下载链接
        file_obj = await doc.get_file()
        file_url = file_obj.file_path

        if not file_url:
            raise Exception("无法获取文件下载链接。")
        # 3. 创建临时文件路径
        temp_dir = tempfile.gettempdir()
        _, ext = os.path.splitext(file_name)
        # 使用唯一文件名防止冲突
        local_path = os.path.join(temp_dir, f"resume_{update.effective_user.id}_{update.message.message_id}{ext}")

        logging.info(f"正在下载：{file_url} -> {local_path}")

        # 4. 异步下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(response.content)

        logging.info(f"✅ 下载成功：{local_path}")
        await loading_message.edit_text("正在提取文本 (可能包含 OCR)...")

        # 再次检查文件是否真的生成了
        if not os.path.exists(local_path):
            # 如果上述方法都没生成文件，尝试最原始的 download (无参数，保存到当前目录)
            # 注意：这可能会保存为 file_id 命名的文件，需要重命名，这里先尝试带参数的
            raise FileNotFoundError("Download method failed to create file.")

        logging.info(f"File downloaded successfully to: {local_path}")

        # 3. 提取文本
        resume_text = extract_text_from_pdf(local_path)

        if not resume_text or len(resume_text.strip()) == 0:
            await loading_message.edit_text(
                "**解析失败**\n\n"
                "未能从文件中提取到任何文字。\n"
                "可能原因：\n"
                "1. 文件是纯图片且 OCR 无法识别\n"
                "2. 文件已加密\n"
                "3. 文件内容为空"
            )
            return

        logging.info(f"File parsed successfully. Length: {len(resume_text)} chars.")

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