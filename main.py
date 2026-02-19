from ceo import CEO

def main():
    print("Personal Ai is Starting...")
    ceo = CEO()

    while True:
        user_input = input("you: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Exiting Personal Ai.")
            break

        response = ceo.receive_command(user_input)
        print("AI: ", response)

if __name__ == "__main__":
    main()