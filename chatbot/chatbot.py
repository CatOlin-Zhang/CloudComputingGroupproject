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

    # 1. Format Pre-check
    if not file_name.lower().endswith(('.pdf', '.doc', '.docx')):
        await update.message.reply_text("Only PDF or Word (.doc/.docx) resumes are supported.")
        return

    loading_message = await update.message.reply_text("📥 Downloading and parsing file...")
    local_path = None
    try:
        # 2. Get download link
        file_obj = await doc.get_file()
        file_url = file_obj.file_path

        if not file_url:
            raise Exception("Unable to retrieve file download link.")

        # 3. Create temporary file path
        temp_dir = tempfile.gettempdir()
        _, ext = os.path.splitext(file_name)
        # Use unique filename to prevent conflicts
        local_path = os.path.join(temp_dir, f"resume_{update.effective_user.id}_{update.message.message_id}{ext}")

        logging.info(f"Downloading: {file_url} -> {local_path}")

        # 4. Asynchronously download file
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(response.content)

        logging.info(f"✅ Download successful: {local_path}")
        await loading_message.edit_text("Extracting text (OCR may be involved)...")

        # Check again if the file was actually generated
        if not os.path.exists(local_path):
            # If the above method fails to generate the file, try the raw download (no params, save to current dir)
            # Note: This might save as a file named with file_id, requiring renaming. Trying with params first here.
            raise FileNotFoundError("Download method failed to create file.")

        logging.info(f"File downloaded successfully to: {local_path}")

        # 3. Extract text
        resume_text = extract_text_from_pdf(local_path)

        if not resume_text or len(resume_text.strip()) == 0:
            await loading_message.edit_text(
                "**Parsing Failed**\n\n"
                "No text could be extracted from the file.\n"
                "Possible reasons:\n"
                "1. File is a pure image and OCR failed\n"
                "2. File is encrypted\n"
                "3. File content is empty"
            )
            return

        logging.info(f"File parsed successfully. Length: {len(resume_text)} chars.")

        # 4. Call RAG Engine
        if rag_engine:
            await loading_message.edit_text("Resume parsing complete. Matching best jobs in database...")

            query_text = resume_text[:2000]
            hits = rag_engine.search(query_text)

            if hits and "Not found" not in hits[0]:
                response_msg = f"Match successful! Based on your resume, recommending the following {len(hits)} positions:\n\n"

                for i, job in enumerate(hits, 1):
                    # Clean newline characters in job string to prevent format chaos
                    clean_job = str(job)
                    response_msg += f"{i}. {clean_job}\n\n"

                response_msg += " You can tell me which one you want to know more about."
                await loading_message.edit_text(response_msg)
            else:
                await loading_message.edit_text(
                    "No perfectly matching positions\n\n"
                    "No positions highly matching your resume were found in the database.\n"
                    "Suggestion: You can try sending the job title or core skills you are interested in directly (e.g., 'Python Developer')."
                )
        else:
            await loading_message.edit_text("Job database not loaded, unable to provide recommendations at the moment.")

    except Exception as e:
        error_msg = str(e).replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
        logging.exception(f"Error processing document {file_name}: {error_msg}")

        await loading_message.edit_text(
            f"Processing Error\n\nAn exception occurred while parsing the file: {error_msg}\n"
            "Please try again later, or send a text description of your requirements directly."
        )

    finally:
        # 5. Clean up temporary file
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
                logging.debug(f"Temp file cleaned: {local_path}")
            except OSError:
                pass

if __name__ == '__main__':
        main()