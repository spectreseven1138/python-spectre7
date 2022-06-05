#!/usr/bin/bash

python3 -m build
pip3 install spectre7 --force-reinstall --no-index --find-links file://$(pwd)/dist
