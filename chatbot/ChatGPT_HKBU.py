# ChatGPT_HKBU.py

import requests
import configparser
import logging

logger = logging.getLogger(__name__)


class ChatGPT:
    def __init__(self, config):
        api_key = config['CHATGPT']['API_KEY']
        base_url = config['CHATGPT']['BASE_URL']
        model = config['CHATGPT']['MODEL']
        api_ver = config['CHATGPT']['API_VER']

        self.url = f'{base_url}/deployments/{model}/chat/completions?api-version={api_ver}'
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        # 基础 System Prompt
        self.base_system_prompt = (
            'You are a helpful Career Assistant for university students. '
            'Your goal is to recommend jobs based SOLELY on the provided "Available Jobs Data". '
            'CRITICAL RULES: '
            '1. NEVER invent or assume any job requirements, skills, certificates, or interview tips that are NOT explicitly in the data. '
            '2. If the data does not contain details about skills/certs/interviews, say: "The database does not provide specific skill requirements for this role." '
            '3. Only use information directly from the data fields: Company, Position, Location, Education, Deadline, Application Link. '
            '4. Do not add examples, explanations, or suggestions unless they are verbatim from the data. '
            '5. Keep replies factual, concise, and grounded in the provided dataset.'
        )

        self.job_context = ""  # 用于存储动态注入的职位数据

    def set_job_context(self, context_text: str):
        """动态设置当前的职位数据上下文，并截断过长内容"""
        # 限制最大长度为 3000 字符
        MAX_CONTEXT_LENGTH = 3000
        if len(context_text) > MAX_CONTEXT_LENGTH:
            logger.warning(f"Job context truncated from {len(context_text)} to {MAX_CONTEXT_LENGTH} chars.")
            self.job_context = context_text[:MAX_CONTEXT_LENGTH] + "\n... [数据已截断]"
        else:
            self.job_context = context_text

    def submit(self, user_message: str):
        system_content = self.base_system_prompt
        if self.job_context:
            # 添加分隔符，避免与 base prompt 混淆
            system_content += f"\n\n--- Available Jobs Data (Max 3000 chars) ---\n{self.job_context}\n--- End of Data ---"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "messages": messages,
            "temperature": 1,
            "max_tokens": 800,
            "top_p": 0.9,
            "stream": False
        }

        try:
            response = requests.post(self.url, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()

            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            # 如果是 400 错误，尝试打印响应体获取详细信息
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"API Error Detail: {error_detail}")
                    return f"抱歉，API 返回错误：{error_detail.get('error', {}).get('message', '未知错误')}"
                except:
                    pass
            logger.error(f"API Request failed: {e}")
            return f"抱歉，连接智能助手时出错：{str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "抱歉，发生了一些意外错误，请稍后再试。"