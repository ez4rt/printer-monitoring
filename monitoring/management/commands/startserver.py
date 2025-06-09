from django.core.management.base import BaseCommand
import subprocess


class Command(BaseCommand):
    help = 'Starts the server and executes additional commands'

    def handle(self, *args, **options):
        commands = [
            ['python', 'manage.py', 'runserver', '0.0.0.0:8000'],
            ['python', 'manage.py', 'bot'],
            ['celery', '-A', 'core', 'worker', '--loglevel=info', '-f', 'logs/automation.log'],
            ['celery', '-A', 'core', 'beat', '-l', 'info', '-f', 'logs/automation.log']
        ]
        for command in commands:
            subprocess.Popen(command)
            self.stdout.write(self.style.NOTICE(f'Running the command: {" ".join(command)}'))
        self.stdout.write(self.style.SUCCESS('The server is running'))


