# ChatGPT_HKBU.py
import requests
import logging
from config import LLMConfig, load_secrets

logger = logging.getLogger(__name__)


class ChatGPT:
    def __init__(self, config_ini_data=None):
        # 如果没有传入 config 对象，则直接从 secrets 加载
        if config_ini_data is None:
            secrets = load_secrets()
            api_key = secrets['CHATGPT_API_KEY']
            base_url = secrets['CHATGPT_BASE_URL']
            model = secrets['CHATGPT_MODEL']
            api_ver = secrets['CHATGPT_API_VER']
        else:
            # 兼容旧代码，如果传入了 configparser 对象
            api_key = config_ini_data['CHATGPT']['API_KEY']
            base_url = config_ini_data['CHATGPT']['BASE_URL']
            model = config_ini_data['CHATGPT']['MODEL']
            api_ver = config_ini_data['CHATGPT']['API_VER']

        self.url = f'{base_url}/deployments/{model}/chat/completions?api-version={api_ver}'
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        self.base_system_template = LLMConfig.SYSTEM_PROMPT_TEMPLATE
        self.job_context = ""

    def set_job_context(self, context_text: str):
        self.job_context = context_text if context_text else "No relevant job data retrieved."

    def submit(self, user_message: str):
        # 动态填充 Prompt 模板
        system_content = self.base_system_template.format(context=self.job_context)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "messages": messages,
            "temperature": LLMConfig.TEMPERATURE,
            "max_tokens": LLMConfig.MAX_TOKENS,
            "top_p": LLMConfig.TOP_P,
            "stream": False
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=LLMConfig.TIMEOUT
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            logger.error(f"API Request failed: {e}")


            error_detail = "未知错误"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    resp_json = e.response.json()

                    if 'error' in resp_json:
                        error_detail = resp_json['error'].get('message', str(resp_json['error']))
                        logger.error(f"API 详细错误信息：{error_detail}")
                    else:
                        error_detail = str(resp_json)
                except Exception:
                    error_detail = e.response.text

            # 返回给用户看的消息
            return f"⚠️ 系统出错：{error_detail}"

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "抱歉，发生了一些意外错误。"
            return "An unexpected error occurred."