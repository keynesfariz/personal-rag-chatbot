import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from services.llm_factory import LLMFactory

async def main():
    llm = LLMFactory.get_llm(provider="gemini")
    messages = [
        SystemMessage(content="You are Farsisstant"),
        HumanMessage(content="Hello")
    ]
    try:
        async for chunk in llm.astream(messages):
            print(chunk.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
