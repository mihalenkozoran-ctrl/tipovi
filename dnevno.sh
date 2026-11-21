#!/bin/bash
cd /root/tipovi
. venv/bin/activate
python fetch.py
python settle.py
python fetch_odds.py
python tiketi.py
