"""ChatGPT cleaning engine for sending prompts and getting responses."""

import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class ChatGPTCleaningEngine:
    """Simple engine for sending prompts to ChatGPT and getting responses."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """Initialize ChatGPT cleaning engine.
        
        Args:
            api_key: OpenAI API key
            model: ChatGPT model to use for cleaning
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
        
        logger.info(f"ChatGPTCleaningEngine initialized with model: {model}")
    
    async def send_prompt(self, prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """Send a prompt to ChatGPT and get the response.
        
        Args:
            prompt: Prompt to send to ChatGPT
            temperature: Temperature for response generation (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Response text from ChatGPT
            
        Raises:
            Exception: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ChatGPT API error: {response.status} - {error_text}")
                
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip() 