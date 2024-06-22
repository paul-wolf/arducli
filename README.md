We assume you have an ardupilot flight controller plugged into a USB port and this is recognised by your workstation.

Create a virtual environment, source it and upgrade pip:

  python -m venv .venv && source .venv/bin/activate && pip install --upgrade pip

Install dependencies:

  pip install -r requirements.txt

Start the cli:

  .venv/bin/python cli.py

