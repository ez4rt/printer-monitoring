from django.test import TestCase
from unittest.mock import patch
import os
from automation.clear_logs import LogsFileManager


class TestLogsFileManager(TestCase):
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('subprocess.run')
    def setUp(self, mock_run, mock_getsize, mock_isfile, mock_listdir):
        self.directory = '/path/to/test/directory'

        mock_listdir.return_value = ['file1.log', 'file2.log', 'file3.log']
        mock_isfile.side_effect = lambda x: x in [os.path.join(self.directory, 'file1.log'), os.path.join(self.directory, 'file2.log')]
        mock_getsize.side_effect = lambda x: 5_000_000 if x == os.path.join(self.directory, 'file1.log') else 15_000_000

        self.logs_file_manager = LogsFileManager(self.directory)

    def test_get_file_names(self):
        self.assertEqual(self.logs_file_manager.file_names, ['file1.log', 'file2.log', 'file3.log'])

    def test_get_file_paths(self):
        expected_paths = [
            os.path.join(self.directory, 'file1.log'),
            os.path.join(self.directory, 'file2.log')
        ]
        self.assertEqual(self.logs_file_manager.file_paths, expected_paths)

    def test_get_file_sizes(self):
        expected_sizes = {
            os.path.join(self.directory, 'file1.log'): 5_000_000,
            os.path.join(self.directory, 'file2.log'): 15_000_000
        }
        self.assertEqual(self.logs_file_manager.file_sizes, expected_sizes)

    @patch('subprocess.run')
    def test_clear_log(self, mock_run):
        file_path = os.path.join(self.directory, 'file2.log')
        self.logs_file_manager.clear_log(file_path)
        mock_run.assert_called_once_with(
            f'truncate -s {self.logs_file_manager.MAX_FILE_SIZE} {file_path}',
            shell=True,
            check=True
        )
