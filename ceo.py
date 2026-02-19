class CEO:
    def __init__(self):
        print("[system] CEO Initialized")

    def receive_command(self, command: str):
        intent = self.process_command(command)           # intent means goal or purpose behind action
        response = self.generate_response(intent, command)
        return response

    def process_command(self, command: str):
        command = command.lower()

        if "write" in command:
            return "wrting"
        
        elif "research" in command:
            return "research"
        
        else:
            return "general"
        
    def generate_response(self, intent, command):
        if intent == "writing":
            return "Detected Writing Task."
        
        elif intent == "research":
            return "Detected Research Task."
        
        else:
            return "General Command Received"
        
# print(CEO())