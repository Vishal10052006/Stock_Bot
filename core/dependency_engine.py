class DependencyEngine:

    def assign_dependencies(self, tasks):
        for task in tasks:
            name = task["task"].lower()

            if "interface" in name:
                task["depends_on"] = ["Build core AI logic"]

            elif "deploy" in name:
                task["depends_on"] = ["Test and debug system"]

            else:
                task["depends_on"] = []

        return tasks