import subprocess
import time


def run_tests():
    commands = [
        "coverage run -p manage.py test tests.monitoring.test_admin",
        "coverage run -p manage.py test tests.monitoring.test_forms",
        "coverage run -p manage.py test tests.monitoring.test_models",
        "coverage run -p manage.py test tests.monitoring.test_signals",
        "coverage run -p manage.py test tests.monitoring.test_tasks",
        "coverage run -p manage.py test tests.monitoring.test_views",
        "coverage run -p manage.py test tests.tgbot",
        "coverage run -p manage.py test tests.monitoring.test_functional.DataLoadTest",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestLoginFunctionality",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestLogoutFunctionality",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestChangePasswordFunctionality",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestMainPageValues",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestNavigationFromMainToSinglePrinter",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestNavigationFromMainToReports",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestNavigationFromMainToEvents",
        # "coverage run -p manage.py test tests.monitoring.test_functional.TestNavigationFromMainToForecast",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestChangeTheme",
        "coverage run -p manage.py test tests.monitoring.test_functional.TestExportReport",
        "coverage run -p manage.py test tests.automation",
        "coverage combine",
        "coverage report",
        "coverage html"
    ]

    for command in commands:
        print(f"Выполнение команды: {command}")
        subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    # python -m tests.run_tests
    start_time = time.time()
    run_tests()
    end_time = time.time()

    elapsed_time = end_time - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    formatted_time = f"{minutes:02}:{seconds:02}"

    print(f"Время выполнения тестов: {formatted_time}")