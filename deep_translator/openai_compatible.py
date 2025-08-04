import json
import time
import os
import logging

from .chatgpt import ChatGptTranslator

logging.basicConfig(
    filename='application.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s'
)

class OpenAICompatibleTranslator(ChatGptTranslator):
    """Translator that handles OpenAI compatible APIs with better error handling
    
    Supports both remote APIs (with API keys) and local models (without API keys).
    """
    
    def __init__(self, source="en", target="zh-CN", **kwargs):
        super().__init__(source=source, target=target, **kwargs)
        self.retry_count = 3
        self.retry_delay = 1  # seconds

    def translate(self, text: str, **kwargs) -> str:
        """
        Translate text with retry mechanism and error handling
        """
        if not text.strip():
            return text

        # Log whether we're using local or remote model
        model_type = "local" if not self.api_key else "remote"
        logging.info(f"Using {model_type} model with base_url: {self.base_url}")

        for attempt in range(self.retry_count):
            try:
                return super().translate(text, **kwargs)
            except json.JSONDecodeError:
                logging.warning(f"Translation API response JSONDecodeError, attempt {attempt + 1}/{self.retry_count}")
                if attempt == self.retry_count - 1:
                    logging.error(f"Translation API response error after {self.retry_count} attempts, using original text")
                    return text
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"Translation error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.retry_count - 1:
                    logging.error(f"Translation failed after {self.retry_count} attempts, using original text")
                    return text
                time.sleep(self.retry_delay)