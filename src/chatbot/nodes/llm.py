import os

from dotenv import load_dotenv
# from langchain_cerebras import ChatCerebras
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from pydantic import SecretStr

load_dotenv()


class LLM:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", ""),
            api_key=SecretStr(os.getenv("OPENAI_API_KEY", "")),
            base_url=os.getenv('BASE_URL', ''),
            temperature=0,
        )

    async def generate(self, messages):
        return await (self.llm | StrOutputParser()).ainvoke(messages)


if __name__ == "__main__":
    import asyncio
    async def test():
        llm = LLM()
        res = await llm.generate("what is machine learning?")
        print(res)
    asyncio.run(test())
