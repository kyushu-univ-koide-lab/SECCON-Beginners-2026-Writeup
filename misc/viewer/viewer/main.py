import os
import sys
import unicodedata


FILES_DIR = "/app/files"
ALLOWED_FILES = {"readme.txt", "hello.txt", "flag.txt"}
MAX_FILENAME_LENGTH = 64
BANNER = r"""
__     ___                        
\ \   / (_) _____      _____ _ __ 
 \ \ / /| |/ _ \ \ /\ / / _ \ '__|
  \ V / | |  __/\ V  V /  __/ |   
   \_/  |_|\___| \_/\_/ \___|_|   
"""


def read_limited(prompt, max_length):
    sys.stdout.write(prompt)
    sys.stdout.flush()

    line = sys.stdin.readline(max_length + 2)
    if not line:
        sys.exit()

    value = line.rstrip("\r\n")
    if len(value) > max_length or (not line.endswith("\n") and len(line) > max_length):
        print("invalid path")
        sys.exit()

    return value.strip()


def resolve_path(filename):
    normalized = unicodedata.normalize("NFKC", filename)

    if normalized != os.path.basename(normalized):
        return None, "invalid path"
    if normalized not in ALLOWED_FILES:
        return None, "file not found"

    path = os.path.normpath(os.path.join(FILES_DIR, normalized))
    if os.path.commonpath([FILES_DIR, path]) != FILES_DIR:
        return None, "invalid path"

    return path, None


def main():
    print(BANNER)
    print("available files:")
    print("- readme.txt")
    print("- hello.txt")

    filename = read_limited("filename > ", MAX_FILENAME_LENGTH)

    if "flag" in filename:
        print("blocked")
        return

    path, error = resolve_path(filename)
    if error is not None:
        print(error)
        return

    try:
        with open(path, encoding="utf-8") as f:
            print(f.read(), end="")
    except (FileNotFoundError, IsADirectoryError):
        print("file not found")


if __name__ == "__main__":
    main()
