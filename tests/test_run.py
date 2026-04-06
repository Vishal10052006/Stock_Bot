import asyncio
from core.ceo import CEO   # adjust if your import path is different

async def main():
    ceo = CEO()
    await ceo.act("Write a blog about AI")

asyncio.run(main())