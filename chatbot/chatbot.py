from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import configparser
import logging
from ChatGPT_HKBU import ChatGPT
from job_database import get_all_jobs_as_text
gpt = None

def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    
    logging.info('INIT: Loading configuration...')
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    global gpt
    gpt = ChatGPT(config)

    job_data = get_all_jobs_as_text()
    gpt.set_job_context(job_data)
    logging.info(f"AI loaded {len(job_data)} chars of job data.")

    logging.info('INIT: Connecting the Telegram bot...')
    app = ApplicationBuilder().token(config['TELEGRAM']['ACCESS_TOKEN']).build()

    logging.info('INIT: Registering handlers...')
    
    # 1. 处理文本消息
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # 2. 处理文档消息 (简历)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logging.info('INIT: Initialization done!')
    app.run_polling()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logging.info(f"USER TEXT: {user_text}")
    
    loading_message = await update.message.reply_text('🤔 正在思考并查询职位库...')

    current_jobs = get_all_jobs_as_text()
    gpt.set_job_context(current_jobs)
    
    response = gpt.submit(user_text)
    
    await loading_message.edit_text(response)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_name = doc.file_name
    
    logging.info(f"USER FILE: {file_name}")
    loading_message = await update.message.reply_text(f'📄 收到简历 `{file_name}`，正在分析匹配度...\n(注意：当前版本仅模拟分析，需接入OCR/PDF解析库才能读取具体内容)')

    prompt = f"用户上传了一份名为 '{file_name}' 的简历。由于技术限制，我暂时无法直接读取文件内容。请礼貌地告诉用户：已收到文件，但请他们直接用文字描述他们的专业、意向城市和期望职位，以便我进行精准推荐。"

    response = gpt.submit(prompt)
    
    await loading_message.edit_text(response)

if __name__ == '__main__':
    main()