from workers.base_worker import BaseWorker


class MathWorker(BaseWorker):

    name = "math_worker"

    capabilities = ["math", "calculate"]

    def run(self, task):
        expression = task["input"]
        return eval(expression)