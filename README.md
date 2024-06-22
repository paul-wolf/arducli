We assume you have an ardupilot flight controller plugged into a USB port and this is recognised by your workstation.

Create a virtual environment, source it and upgrade pip:

  python -m venv .venv && source .venv/bin/activate && pip install --upgrade pip

Install dependencies:

  pip install -r requirements.txt

Start the cli:

  .venv/bin/python cli.py

You have these commands from the cli:

connect: connect to a port

disconnect: disconnect from a port

dump: dump all parameters

exit: exit the cli

get: get a parameter value. This takes regular expressions

help: show help

info: show info about the connected device

quit: exit the cli

set: set the value of a parameter. This writes to the flight controller