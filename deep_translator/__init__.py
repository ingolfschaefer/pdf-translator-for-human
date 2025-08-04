"""Top-level package for Deep Translator"""

__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

from deep_translator.chatgpt import ChatGptTranslator
from deep_translator.openai_compatible import OpenAICompatibleTranslator

__author__ = """Nidhal Baccouri"""
__email__ = "nidhalbacc@gmail.com"
__version__ = "1.9.1"

__all__ = [
    "ChatGptTranslator",
    "OpenAICompatibleTranslator",
]