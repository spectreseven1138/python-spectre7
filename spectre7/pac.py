#!/usr/bin/python3
# Convenience wrapper for Pacman

import os
from spectre7 import utils

PACKAGE_DOWNLOAD_PATH = "/tmp/pac-packages"

def call(args: list):
	command = "sudo pacman "
	if len(args) > 0:
		if args[0].startswith("-"):
			pass
		elif args[0].endswith(".pkg.tar.zst") or args[0].endswith(".tar.xz") or args[0].endswith(".tar.gz"):
			command += "-U "
		elif args[0].startswith("https://archlinux.org/packages/"):
			url = args[0]
			args.clear()

			if not url.endswith("/download"):
				url = os.path.join(url, "download")

			# https://archlinux.org/packages/extra/x86_64/kconfigwidgets/

			utils.ensureDirExists(PACKAGE_DOWNLOAD_PATH)

			file = url.removeprefix("https://archlinux.org/packages/").removesuffix("/download").replace("/", ".")
			file = os.path.join(PACKAGE_DOWNLOAD_PATH, file + ".pkg.tar.zst")

			if not os.path.isfile(file):
				os.system(f"wget -O {file} {url}")

			command += f"-U {file}"
		else:
			command += "-S "
		for arg in args:
			command += arg + " "

	os.system(command)

def main():
	import sys

	args = sys.argv
	args.pop(0)
	
	call(args)

if __name__ == "__main__":
	main()