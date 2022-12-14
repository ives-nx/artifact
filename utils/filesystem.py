import subprocess
import os
from os import mkdir, getcwd
from os.path import exists, split, join
from shutil import rmtree
from typing import Generator, List, Tuple


def get_config_directory() -> str:
    cur_working_directory = getcwd()
    # path, last_folder = split(cur_working_directory)
    
    # while last_folder != "deepwukong":
    #     path, last_folder = split(path)
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    last_dir = os.path.dirname(cur_dir)
    return join(last_dir, "configs")


def count_lines_in_file(file_path: str) -> int:
    command_result = subprocess.run(["wc", "-l", file_path],
                                    capture_output=True,
                                    encoding="utf-8")
    if command_result.returncode != 0:
        raise RuntimeError(
            f"Counting lines in {file_path} failed with error\n{command_result.stderr}"
        )
    return int(command_result.stdout.split()[0])