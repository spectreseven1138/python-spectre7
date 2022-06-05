#!/usr/bin/python3
# Convenience wrapper for Pacman

import os

PACKAGE_DOWNLOAD_PATH = "/tmp/pac-package.pkg.tar.zst"

def call(args: list):
        command = "sudo pacman "
        if len(args) > 0:
                if args[0].startswith("-"):
                        pass
                elif args[0].endswith(".pkg.tar.zst") or args[0].endswith(".tar.xz") or args[0].endswith(".tar.gz"):
                        command += "-U "
                elif args[0].startswith("https://"):
                        url = args[0]
                        args.clear()

                        if url.startswith("https://archlinux.org/packages/") and not url.endswith("/download"):
                                url = os.path.join(url, "download")

                        os.system(f"wget -O {PACKAGE_DOWNLOAD_PATH} {url}")
                        command += f"-U {PACKAGE_DOWNLOAD_PATH} && rm {PACKAGE_DOWNLOAD_PATH}"
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