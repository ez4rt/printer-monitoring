import os
import subprocess


class LogsFileManager:
    def __init__(self, directory: str):
        self.directory = directory
        self.MAX_FILE_SIZE = 10_485_760
        self.file_names = self.get_file_names()
        self.file_paths = self.get_file_paths()
        self.file_sizes = self.get_file_sizes()

    def get_file_names(self) -> list:
        return os.listdir(self.directory)

    def get_file_paths(self) -> list:
        file_paths = list()

        for file_name in self.file_names:
            file_path = os.path.join(self.directory, file_name)
            if os.path.isfile(file_path):
                file_paths.append(file_path)

        return file_paths

    def get_file_sizes(self) -> dict:
        file_sizes = dict()

        for file_path in self.file_paths:
            file_size = os.path.getsize(file_path)
            file_sizes[file_path] = file_size

        return file_sizes

    def check_size(self):
        for file_path, size in self.file_sizes.items():
            if size > self.MAX_FILE_SIZE:
                self.clear_log(file_path)

    def clear_log(self, file_path):
        command = f'truncate -s {self.MAX_FILE_SIZE} {file_path}'
        subprocess.run(command, shell=True, check=True)

