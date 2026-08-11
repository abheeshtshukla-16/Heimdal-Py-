from pydantic import BaseModel
from typing import Literal


class OpenAIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class OpenAIChoices(BaseModel):
    index: int
    message: OpenAIMessage
    finish_reason: str


class OpenAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAI(BaseModel):
    model: str
    messages: list[OpenAIMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    stream: bool | None = None


class OpenAIResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[OpenAIChoices]
    usage: OpenAIUsage
