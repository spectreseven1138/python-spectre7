#!/usr/bin/bash

python -m build
pip install spectre7 --force-reinstall --no-index --find-links file://$(pwd)/dist --break-system-packages
