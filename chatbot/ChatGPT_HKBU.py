import requests
import logging
from config import LLMConfig, load_secrets

logger = logging.getLogger(__name__)


class ChatGPT:
    def __init__(self, config_ini_data=None):
        # If no config object is passed in, load directly from secrets
        if config_ini_data is None:
            secrets = load_secrets()
            api_key = secrets['CHATGPT_API_KEY']
            base_url = secrets['CHATGPT_BASE_URL']
            model = secrets['CHATGPT_MODEL']
            api_ver = secrets['CHATGPT_API_VER']
        else:
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
        # Prompt Template
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


            error_detail = "Unknown error"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    resp_json = e.response.json()

                    if 'error' in resp_json:
                        error_detail = resp_json['error'].get('message', str(resp_json['error']))
                        logger.error(f"API detailed error information：{error_detail}")
                    else:
                        error_detail = str(resp_json)
                except Exception:
                    error_detail = e.response.text

            # Message returned to the user
            return f"System error：{error_detail}"

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "An unexpected error occurred."