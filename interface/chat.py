# interface/chat.py

from core.ceo import CEO

ceo = CEO()

def chat(user_input: str):
    """
    Main communication entry for Mother AI
    """
    response = ceo.handle(user_input)
    return response


# simple test run
if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        output = chat(user_input)
        print("AI:", output)