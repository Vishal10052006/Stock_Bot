import asyncio
from core.ceo import CEO

async def main():
    print("Personal AI is Starting...")
    ceo = CEO()

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Exiting Personal AI.")
            break

        response = await ceo.receive_command(user_input)
        print(response)

if __name__ == "__main__":
    asyncio.run(main())
