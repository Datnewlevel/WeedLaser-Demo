#!/bin/bash
python -m pip install --upgrade pip
pip install --default-timeout=1000 tflite-runtime
git clone https://github.com/tensorflow/examples.git --depth 1
echo "Done!”
