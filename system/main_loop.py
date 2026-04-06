from core.ceo import CEO

def run():
    ceo = CEO()

    while True:
        task = input("Enter task: ")
        result = ceo.handle(task)
        print("AI:", result)