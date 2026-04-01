import asyncio
from core.ceo import CEO

async def main():
    ceo = CEO()

    for i in range(3):
        print(f"\nRUN {i+1}")
        await ceo.act("analyze stock: RELIANCE")

asyncio.run(main())