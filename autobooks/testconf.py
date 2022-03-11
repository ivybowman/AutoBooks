import glob
import os
import shutil
import sys
from configparser import ConfigParser
from configobj import ConfigObj
from datetime import datetime
from pathlib import Path
from time import sleep
from unittest.mock import patch
import json
import cronitor
import odmpy.odm as odmpy
import pandas as pd
import requests
import selenium
from loguru import logger

script_dir = os.path.join(Path.home(), "AutoBooks")
#config = ConfigObj(os.path.join(script_dir, "autobooks.ini"))
# Read config file
parser = ConfigParser()
parser.read(os.path.join(script_dir, "autobooks.ini"))
print(parser.sections())
section = parser.default_section
print(section.get('odm_folder'))
print(parser)
#print(config.keys())
#odm_dir = parser.get("DEFAULT", "odm_folder")
#out_dir = parser.get("DEFAULT", "out_folder")
#library_count = len(parser.sections())
# Cronitor Setup https://cronitor.io/
#cronitor.api_key = parser.get("DEFAULT", "cronitor_apikey")
#monitor = cronitor.Monitor(parser.get("DEFAULT", "cronitor_name_main"))