__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import os
from typing import List, Optional

from deep_translator.base import BaseTranslator
from deep_translator.constants import (
    OPEN_AI_ENV_VAR,
    OPEN_AI_BASE_URL_ENV_VAR,
    OPEN_AI_MODEL_ENV_VAR,
)


class ChatGptTranslator(BaseTranslator):
    """
    class that wraps functions, which use the ChatGPT
    under the hood to translate word(s)
    """

    def __init__(
        self,
        source: str = "auto",
        target: str = "english",
        api_key: Optional[str] = os.getenv(OPEN_AI_ENV_VAR, None),
        model: Optional[str] = os.getenv(OPEN_AI_MODEL_ENV_VAR, "gpt-4o-mini"),
        base_url: Optional[str] = os.getenv(OPEN_AI_BASE_URL_ENV_VAR, None),
        **kwargs,
    ):
        """
        @param api_key: your openai api key. Can be None for local models.
        @param source: source language
        @param target: target language
        @param model: OpenAI model to use
        @param base_url: custom OpenAI API base URL
        """
        # Allow empty/None API key for local models
        self.api_key = api_key if api_key else None
        self.model = model
        self.base_url = base_url

        super().__init__(source=source, target=target, **kwargs)

    def translate(self, text: str, **kwargs) -> str:
        """
        @param text: text to translate
        @return: translated text
        """
        import openai

        # For local models, api_key can be None or empty string
        # The OpenAI client will handle this appropriately
        client_kwargs = {}
        
        # Only set api_key if it's provided (not None or empty)
        if self.api_key:
            client_kwargs["api_key"] = self.api_key
        else:
            # For local models, use a placeholder or None
            client_kwargs["api_key"] = "local-model"
            
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = openai.OpenAI(**client_kwargs)

        prompt = f"Translate the text below into {self.target}. Do not give explanations. Just the translation. No introductory text before.\n"
        prompt += f'Text: "{text}"'

        # if model is empty (for mlx_lm.server, the model should be default_model)
        # export OPENAI_MODEL=default_model
        response = client.chat.completions.create(
            model=self.model if self.model else "default_model",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        
        return response.choices[0].message.content

    def translate_file(self, path: str, **kwargs) -> str:
        return self._translate_file(path, **kwargs)

    def translate_batch(self, batch: List[str], **kwargs) -> List[str]:
        """
        @param batch: list of texts to translate
        @return: list of translations
        """
        return self._translate_batch(batch, **kwargs)