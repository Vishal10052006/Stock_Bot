import asyncio
from core.ceo import CEO

async def test_phase4():
    ceo = CEO()

    for i in range(3):
        print(f"\nRUN {i+1}")
        await ceo.act("write a blog about AI")

async def main():
    print("Personal AI is Starting...")
    ceo = CEO()

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Exiting Personal AI.")
            break

        response = await ceo.act(user_input)
        print(response)

if __name__ == "__main__":
    # 👉 TEMPORARY: switch to test mode
    asyncio.run(test_phase4())

    # 👉 Later switch back:
    # asyncio.run(main())