import datetime

def log(message):
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("system.log", "a") as f:
        f.write(f"[{time}] {message}\n")
