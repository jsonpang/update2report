import os
from openai import OpenAI, OpenAIError

class LLMClient:
    def __init__(self):
        base_url = os.getenv('LLM_BASE_URL')
        if not base_url:
            raise RuntimeError('LLM_BASE_URL is required for uncached generation')
        self.client = OpenAI(base_url=base_url, api_key=os.getenv('LLM_API_KEY') or 'ollama', timeout=45, max_retries=1)
        self.model = os.getenv('LLM_MODEL')
        if not self.model:
            raise RuntimeError('LLM_MODEL is required')
        self.total_tokens = 0
    def complete(self, system, user):
        try:
            result = self.client.chat.completions.create(model=self.model, messages=[{'role':'system','content':system},{'role':'user','content':user}], temperature=0.2)
        except OpenAIError:
            raise RuntimeError('The model service is unavailable or timed out after one retry. Please try again later, or load a cached sample.') from None
        if result.usage:
            self.total_tokens += result.usage.total_tokens or 0
        return result.choices[0].message.content or '' if result.choices else ''
