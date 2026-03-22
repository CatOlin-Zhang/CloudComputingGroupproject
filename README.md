# AI Career Assistant Chatbot on telegram

An intelligent job-seeking assistant chatbot based on **Telegram** and **LLM**. It uses **RAG** technology combined with **semantic vector search** to provide job seekers with accurate job recommendations and career consultation services.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-2CA5E0?logo=telegram)
![RAG](https://img.shields.io/badge/RAG-SentenceTransformers-orange?logo=huggingface)
![LLM](https://img.shields.io/badge/LLM-OpenAI_Compatible-green)
![Deployment](https://img.shields.io/badge/Deploy-GitHub_Actions-black?logo=github-actions)

## Project Directory

    AI Career Assistant Chatbot on telegram/
    ├── .github/
    │   └── workflows/
    │       └── deploy.yml          # GitHub Actions automated deployment script
    ├── chatbot/                    # Core Code Directory of Chatbot
    │   ├── bot.log                 # Operation log file (for debugging)
    │   ├── chatbot.py              # Telegram Bot Main Program Entry
    │   ├── ChatGPT_HKBU.py         # LLM API Call Wrapper Module
    │   ├── config.ini              # Telegram Bot ACCESS_Token, GenAI API Key
    │   ├── config.py               # Storage data retrieval path, RAG parameter configuration, core prompts
    │   ├── log_config.py           # Log System Configuration
    │   ├── pdf_processor.py        # PDF processing function
    │   └── rag_engine.py           # RAG Retrieval-Augmented Generation Engine
    ├── JobData/                    # Data storage directory
    │   └── Jobdata.xlsx            # Job Information Database (Excel Format)
    ├── .gitignore                  # Git ignore rules file
    └── README.md                   # Project Description Document

##  What can this robot do?
* **Recommend suitable jobs to you**
    *   **Dialogue as the result**: No need for complicated screening forms. Just describe your needs as if talking to a person, and the bot will immediately understand your intent and return a list of precisely matched positions.
    *   **PDF Resume**: Find text descriptions too troublesome? Simply upload your PDF resume. The bot will automatically analyze your experience, skills, and background, proactively uncovering highly compatible potential opportunities in the database.
* **Career Skills Planning**
    *   **Already have a job in mind but don't know where to start?**: Based on the job you want, the bot will recommend the professional skills you still need to learn.

##  What features does this robot have?
* **Matching database results through user's text messages**
    *   **Vector-database-based RAG**: Uses `Sentence Transformers` for deep vectorization, capable of understanding user intent.
    *   **Neural search**: Can accurately recall relevant positions even if the user's query does not exactly match the job description.
    *   **Multilingual adaptation**: User inputs in different languages (Simplified Chinese or English) can be accurately processed. (More languages can be supported after loading additional language encoders)
* **Reliable Intelligent Q&A**
    *   **Strict Prompt Engineering**: Through strict prompt engineering, force the LLM to answer only based on the real Excel data in the database, and never fabricate salary, benefits, or job requirements.
    *   **Intelligent Safeguard**: When there is indeed no relevant position in the database, the robot will honestly inform 'No matches found' instead of making up false information to mislead users.
    *   **Structured Output**: Automatically organize job titles, companies, locations, deadlines, and application links in a clear and readable format.
* **Telegram integration with 24/7 cloud service support for automated updates**
    *   No need to download extra apps or configure complicated front-end interfaces. Use the native Telegram client to achieve multi-device synchronization on mobile/desktop, and start conversations anytime, anywhere.
    *   After pushing the code to GitHub, it is automatically built and deployed to the cloud server via GitHub Actions, ensuring the service is online 24/7 and always up-to-date.
* **Data Source**
    * **No-Code Update**: Simply update the Excel file and restart the bot to sync the latest data.
    * Supports loading job data directly from an Excel file (`Jobdata.xlsx`).

## ChatBot Command
To make navigation seamless, the bot supports the following commands:
* **(`/start`) - Displays the onboarding welcome message and usage guide.**
* **(`/job`) - Switches to Job Search Mode (Default). Use this to search the database or upload resumes.**
* **(`/skill`) - Switches to Skill Inquiry Mode. Use this to directly ask about the required skills for any specific profession.**

## Quick Start

This project can run without a high-performance GPU. What you need is a computer that can connect to the Internet, a Telegram bot access token, and a Gen AI API.

### 1. Environment Preparation

Make sure Python 3.8 or higher is installed. It is recommended to use a virtual environment to isolate dependencies.

```bash
# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Troubleshooting
Some features require support from specific versions of the software package:
When your operation shows:
*   RAG returns results, but the robot does not output results.
*   The PDF has been uploaded but no content was detected.

#### The following commands can help you solve the problem:
```bash
pip install openpyxl==3.5.5
```
```bash
pip install pypdf==6.8.0
```
