# chatbot.py

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import configparser
import logging
import os
import tempfile
from ChatGPT_HKBU import ChatGPT
from job_database import get_all_jobs_as_text
from resume_parser import extract_text_from_file

gpt = None

# 配置日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logging.info('INIT: Loading configuration...')
    config = configparser.ConfigParser()
    config.read('config.ini')

    global gpt
    gpt = ChatGPT(config)

    # 预加载职位数据
    job_data = get_all_jobs_as_text()
    gpt.set_job_context(job_data)
    logging.info(f"AI initialized with job data.")

    logging.info('INIT: Connecting the Telegram bot...')
    app = ApplicationBuilder().token(config['TELEGRAM']['ACCESS_TOKEN']).build()

    logging.info('INIT: Registering handlers...')

    # 处理文本消息
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 处理文档消息 (PDF, DOCX)
    doc_filter = filters.Document.PDF | filters.Document.DOC | filters.Document.DOCX
    app.add_handler(MessageHandler(doc_filter, handle_document))

    logging.info('INIT: Initialization done!')
    app.run_polling()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"USER TEXT: {user_text}")

    loading_message = await update.message.reply_text('正在查询职位库...')

    # 刷新职位数据
    current_jobs = get_all_jobs_as_text()
    gpt.set_job_context(current_jobs)

    response = gpt.submit(user_text)
    await loading_message.edit_text(response)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_name = doc.file_name
    user_id = update.effective_user.id

    logger.info(f"USER FILE: {file_name} from User {user_id}")

    # 1. 提示用户
    loading_message = await update.message.reply_text(f'📄 收到 `{file_name}`，正在下载并解析简历内容...\n请稍候...')

    # 2. 下载文件到临时目录
    # Telegram 文件需要先下载才能读取
    file_obj = await context.bot.get_file(doc.file_id)

    # 创建一个安全的临时文件名
    temp_dir = tempfile.gettempdir()
    local_file_path = os.path.join(temp_dir, f"{user_id}_{file_name}")

    try:
        # 下载文件
        await file_obj.download_to_drive(local_file_path)
        logger.info(f"File downloaded to: {local_file_path}")

        # 3. 解析文件内容
        await loading_message.edit_text(f'🔍 已下载成功，正在提取 `{file_name}` 中的文字...')
        resume_text = extract_text_from_file(local_file_path)

        if "无法从文件中提取" in resume_text:
            await loading_message.edit_text(
                f"⚠️ 抱歉，无法读取 `{file_name}` 的内容。\n"
                "这可能是因为文件是**扫描版图片**（没有文字层）或已加密。\n"
                "请尝试上传文字版的 PDF/Word，或者直接告诉我您的专业和意向职位。"
            )
            return

        # 4. 构建 Prompt：简历 + 职位库 -> 推荐
        await loading_message.edit_text('正在分析匹配度并生成推荐列表...')

        # 刷新最新的职位数据，确保推荐是实时的
        job_data = get_all_jobs_as_text()

        # 构造专门的 Prompt
        analysis_prompt = (
            f"我是一名求职助手。以下是用户的简历内容：\n\n"
            f"--- RESUME START ---\n{resume_text}\n--- RESUME END ---\n\n"
            f"以下是当前可用的职位数据库：\n\n"
            f"--- JOBS DATA START ---\n{job_data}\n--- JOBS DATA END ---\n\n"
            f"任务：\n"
            f"1. 分析用户的技能、专业、学历和意向城市。\n"
            f"2. 从【JOBS DATA】中筛选出最匹配的 1-3 个职位。\n"
            f"3. 如果没有任何匹配，请礼貌地说明原因（如学历不符、城市不符等），并给出建议。\n"
            f"4. 输出格式：\n"
            f"   - 📝 **简历分析**: (简短总结用户背景)\n"
            f"   - 🎯 **推荐职位**: (列出匹配职位，包含公司、职位、申请链接)\n"
            f"   - 💡 **建议**: (如果有)"
        )

        gpt.set_job_context("")
        response = gpt.submit(analysis_prompt)

        await loading_message.edit_text(response)

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        await loading_message.edit_text(f"处理文件时出错：{str(e)}\n请稍后重试或联系管理员。")

    finally:
        if os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
                logger.debug(f"Temp file cleaned: {local_file_path}")
            except:
                pass


if __name__ == '__main__':
    main()