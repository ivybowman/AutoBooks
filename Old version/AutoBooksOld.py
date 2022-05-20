import glob
import os
import platform
import shutil
import sys
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from time import sleep
from unittest.mock import patch

import cronitor
import odmpy.odm as odmpy
import pandas as pd
import requests
from loguru import logger

from autobooks.utils import InterceptHandler, RedactingFormatter, process_logfile, parse_form, craft_booklist

# Set Vars
version = "0.5"  # Version number of script
error_count = 0
script_dir = os.path.join(Path.home(), "AutoBooks")
csv_path = os.path.join(script_dir, 'web_known_files.csv')

# Check paths, and if not found do first time setup
if os.path.exists(script_dir):
    os.chdir(script_dir)
else:
    os.mkdir(script_dir)
    main_conf = requests.get(
        'https://raw.githubusercontent.com/ivybowman/AutoBooks/main/autobooks_template.ini')
    folders = ['log', 'downloads', 'source_backup']
    for folder in folders:
        os.mkdir(os.path.join(script_dir, folder))
    with open(os.path.join(script_dir, "autobooks.conf"), mode='wb') as local_file:
        local_file.write(main_conf.content)
    print("Finished setup please configure settings in file: ",
          os.path.join(script_dir, "autobooks.conf"))
    sys.exit(1)

# Logging Config
LOG_PATH = os.path.join(script_dir, 'log')
LOG_FILENAME = os.path.join(
    script_dir, 'log', 'AutoBooks-{:%H-%M-%S_%m-%d}.log'.format(datetime.now()))

patterns = ['[34m[1m', '[39m[22m', '[34m[22m', '[35m[22m']
console_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {message}\n{exception}"
cronitor_log_format = "[{name}:{function}] {level}: {message}\n{exception}"
file_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {extra[scrubbed]}\n{exception}"
redacting_formatter = RedactingFormatter(patterns=patterns, source_fmt=file_log_format)
logger.configure(handlers=[
    {'sink': sys.stderr, "format": console_log_format},
    {'sink': LOG_FILENAME,
     "format": redacting_formatter.format, "retention": 10},
])
# logging.getLogger().setLevel('DEBUG')
# logging.getLogger().addHandler(InterceptHandler())
odmpy.logger.handlers.clear()
odmpy.logger.addHandler(InterceptHandler())

# Read config file
parser = ConfigParser()
parser.read(os.path.join(script_dir, "autobooks.ini"))
config = parser['DEFAULT']
library_count = len(parser.sections())

# Cronitor Setup https://cronitor.io/
cronitor.api_key = config['cronitor_apikey']
monitor = cronitor.Monitor(config['cronitor_monitor'])


# Function to process the books.
def process(odm_list):
    global error_count
    good_odm_list = []
    bad_odm_list = []
    logger.info('Begin processing book list: {}', " ".join(odm_list))
    for x in odm_list:
        odmpy_args = ["odmpy", "dl", "--nobookfolder"]
        if config['odmpy_test_args'] == "True":
            odmpy_args.extend([x])
        else:
            odmpy_args.extend(["-c", "-m", "--mergeformat", "m4b", x])
        with patch.object(sys, 'argv', odmpy_args):
            try:
                odmpy.run()
            except(FileNotFoundError, FileExistsError) as e:
                logger.error("Error starting odm {} Message: {}", x, e)
            except SystemExit as e:
                bad_odm_list.append(x)
                if os.path.isfile("cover.jpg"):
                    os.remove("cover.jpg")
                error_count += 1
            else:
                good_odm_list.append(x)
    logger.info("Book Processing Finished")
    return good_odm_list, bad_odm_list


# Function to clean up in and out files.
def cleanup(m4b_list, odm_list, odm_folder):
    global error_count
    # Move m4b files to out_dir
    for x in m4b_list:
        if os.path.isfile(os.path.join(config["out_folder"] + x)):
            logger.error("Book {} already exists in out dir skipped", x)
            error_count += 1
        else:
            shutil.move(os.path.join(odm_folder, x), os.path.join(config["out_folder"], x))
            logger.info("Moved book {} to out_dir", x)
    # Backup source files
    for x in odm_list:
        if os.path.isfile(os.path.join(script_dir, "source_backup", x)):
            logger.error(
                "File pair {} already exists in source backup dir skipped", x)
            error_count += 1
        else:
            license_file = x.replace(".odm", ".license")
            shutil.move(x, os.path.join(script_dir, "source_backup", x))
            shutil.move(license_file, os.path.join(script_dir, "source_backup", license_file))
            logger.info("Moved file pair {} to source files", x)


def main_run():
    # AutoBooks
    logger.info("Started AutoBooks V.{} By:IvyB", version)
    # Try to change to ODM folder
    try:
        os.chdir(config["odm_folder"])
    except FileNotFoundError:
        logger.critical("The provided .odm dir was not found, exiting")
        sys.exit(1)
    else:
        odm_list = glob.glob("*.odm")
        monitor.ping(state='run',
                     message=f"AutoBooks by IvyB v.{version} \n"
                             f"logfile: {LOG_FILENAME}\n odm_dir: {config['odm_folder']} \n "
                             f"out_dir: {config['out_folder']} \n"
                             f"odm_list:{odm_list}")

        # Check if any .odm files exist in odm_dir
        if len(odm_list) == 0:
            monitor.ping(state='fail', message='Error: No .odm files found, exiting',
                         metrics={'error_count': error_count})
            logger.critical("No .odm files found, exiting")
            sys.exit(1)
        else:
            good_odm_list, bad_odm_list = process(odm_list)
            # Cleanup files
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, config["odm_folder"])
            # Send complete event and log to Cronitor
            log_str = process_logfile(LOG_FILENAME, terms=(
                "Downloading", "expired", "generating", "merged", "saved"))
            monitor.ping(state='complete', message=log_str,
                         metrics={'count': len(odm_list), 'error_count': error_count})


if __name__ == "__main__" and config["test_run"] == "True":
    main_run()
