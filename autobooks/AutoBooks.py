import glob
import logging
import os
import shutil
import sys
from configparser import ConfigParser
from pathlib import Path
from time import sleep
from unittest.mock import patch

import cronitor
import odmpy.odm as odmpy
import pandas as pd
import requests
from loguru import logger

from utils import InterceptHandler, RedactingFormatter, process_logfile, parse_form, craft_booklist

# Set Vars
version = "0.3"  # Version number of script
error_count = 0
good_odm_list = []
bad_odm_list = []
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
LOG_FILENAME = os.path.join(LOG_PATH, "AutoBooks.log")
patterns = ['[34m[1m', '[39m[22m', '[34m[22m', '[35m[22m']
console_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {message}\n{exception}"
cronitor_log_format = "[{name}:{function}] {level}: {message}\n{exception}"
file_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {extra[scrubbed]}\n{exception}"
redacting_formatter = RedactingFormatter(patterns=patterns, source_fmt=file_log_format)
logger.configure(handlers=[
    {'sink': sys.stderr, "format": console_log_format},
    {'sink': LOG_FILENAME,
     "format": redacting_formatter.format, "retention": 10, "rotation": "1 day"},
])
# logging.getLogger().setLevel('DEBUG')
# logging.getLogger().addHandler(InterceptHandler())
odmpy.logger.handlers.clear()
odmpy.logger.addHandler(InterceptHandler())

# Read config file
parser = ConfigParser()
parser.read(os.path.join(script_dir, "autobooks.ini"))
config = parser['DEFAULT']
odm_dir = config["odm_folder"]
out_dir = config["out_folder"]
library_count = len(parser.sections())
# Cronitor Setup https://cronitor.io/
cronitor.api_key = config['cronitor_apikey']
monitor = cronitor.Monitor(config['cronitor_monitor'])


# Function to process the books.
def process(odm_list):
    global error_count
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
            except FileNotFoundError:
                logger.error("Could not find odm file {}", x)
            except FileExistsError:
                logger.error("FileAlreadyExists, likely from m4b creation attempt")
            except SystemExit as e:
                bad_odm_list.append(x)
                if os.path.isfile("cover.jpg"):
                    os.remove("cover.jpg")
                error_count += 1
            else:
                good_odm_list.append(x)
    logger.info("Book Processing Finished")


# Function to clean up in and out files.
def cleanup(m4b_list, odm_list, odm_folder):
    global error_count
    # Move m4b files to out_dir
    for x in m4b_list:
        if os.path.isfile(os.path.join(out_dir + x)):
            logger.error("Book {} already exists in out dir skipped", x)
            error_count += 1
        else:
            shutil.move(os.path.join(odm_folder, x), os.path.join(out_dir, x))
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


def web_login(subdomain, card_num, pin, select):
    login_session = requests.Session()
    box = login_session.get(f'https://{subdomain}.overdrive.com/account/ozone/sign-in?forward=%2F')
    form_list = parse_form(box, "loginForms")['forms']
    if len(form_list) == 1:
        x = 0
    else:
        for form in form_list:
            if select in form['displayName']:
                print(select, "Matches: ", form['displayName'], "ils:", form['ilsName'])
                x = form_list.index(form)
                break
    sleep(0.5)
    auth = login_session.post(f'https://{subdomain}.overdrive.com/account/signInOzone',
                              params=(('forwardUrl', '/'),),
                              data={
                                  'ilsName': form_list[x]['ilsName'],
                                  'authType': form_list[x]['type'],
                                  'libraryName': form_list[x]['displayName'],
                                  'username': card_num,
                                  'password': pin
                              })
    # print("AUTH URL: ", auth.url)
    return auth.url, form_list[x]['ilsName'], login_session


# Function to download loans from OverDrive page
def web_dl(df, session, base_url, name, book_list):
    global error_count
    df_out = pd.DataFrame()
    logger.info("Begin DL from library: {} ", name)
    odm_list = []
    book_count = 0
    if len(book_list) == 0:
        logger.warning("Can't find books skipped library: {}", name)
        error_count += 1
        return df_out
    for book in book_list:
        if book['format'] != "ebook-overdrive":
            print("AudioBook Info: ", book['title'], "-", book['id'], "-", book['format'])
            id_query = df.query('book_id == ' + book['id'])
            if id_query.empty is False:
                logger.info('Skipped "{}" found in known books', book['title'])
            else:
                # Short wait then download ODM
                sleep(0.5)
                odm = session.get(f'{base_url}media/download/audiobook-mp3/{book["id"]}')
                odm_filename = odm.url.split("/")[-1].split('?')[0]
                with open(odm_filename, "wb") as f:
                    f.write(odm.content)
                odm_list.append(odm_filename)
                print(odm_filename)
                # Save book info to dataframe
                df_book = pd.DataFrame([[name, book['id'], book['title'], odm_filename]],
                                       columns=['ils_name', 'book_id', 'book_title', 'book_odm'])
                df_out = pd.concat([df_out, df_book])
                logger.info("Downloaded book: {} as {}", book['title'], odm_filename)
    sleep(1)
    logger.info("Finished downloading {} books from library {}",
                book_count, name)
    return df_out, odm_list


# AutoBooks Web Code
def web_run():
    global error_count
    web_odm_list = []
    if len(parser.sections()) == 0:
        logger.critical("No libraries configured!")
        sys.exit(1)
    else:
        logger.info("Started AutoBooks Web V.{} By:IvyB", version)
        monitor.ping(state='run',
                     message=(f'AutoBooks Web by IvyB V.{version} \n'
                              f'logfile: {LOG_FILENAME} \n LibraryCount: {str(library_count)}'))

        # Attempt to read known files csv for checking books
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, sep=",")
        else:
            # Failing above create an empty df for checking
            df = pd.DataFrame({
                'book_id': [''],
            })
        os.chdir(os.path.join(script_dir, "downloads"))

        # For every library, open site, attempt sign in, and attempt download.
        for i in range(0, library_count):
            lib_conf = parser['library_' + str(i)]
            logger.info("Started library {}", lib_conf['library_name'])
            sleep(3)
            base_url, ils_name, session = web_login(lib_conf['library_subdomain'],
                                                    lib_conf['card_number'],
                                                    lib_conf['card_pin'],
                                                    lib_conf['library_select'], )
            if not base_url.endswith('/'):
                base_url = base_url+'/'
            loans = session.get(f'{base_url}account/loans')
            if loans.status_code == 200:
                book_list = craft_booklist(loans)
                if len(book_list) != 0:
                    df_out, odm_list = web_dl(df, session, base_url, ils_name, book_list)
                    if web_odm_list == [] and odm_list != []:
                        web_odm_list = odm_list
                    else:
                        web_odm_list.extend(odm_list)
                    print(odm_list)
                    print("Web:")
                    print(web_odm_list)
                    sleep(2)
                    if os.path.isfile(csv_path):
                        df_out.to_csv(csv_path, mode='a', index=False, header=False)
                    else:
                        df_out.to_csv(csv_path, mode='w', index=False, header=True)
                else:
                    logger.warning("Can't find books skipped library: {}", lib_conf['library_name'])
                    error_count += 1
        logger.info("AutoBooksWeb Complete")
        print(web_odm_list)
        #web_odm_list = glob.glob("*.odm")

        # Process log file for Cronitor.
        process_logfile(LOG_FILENAME, terms=("web", "ERROR"))
        monitor.ping(state='complete', message="".join(web_odm_list),
                     metrics={'count': len(web_odm_list), 'error_count': error_count})

        # Call DL to process odm files from web
        if len(web_odm_list) != 0 and 4 + 5 == 10:
            logger.info("Started AutoBooks V.{} By:IvyB", version)
            monitor.ping(state='run',
                         message=f"AutoBooks by IvyB v.{version} \n"
                                 f"logfile: {LOG_FILENAME}\n odm_dir: {odm_dir} \n out_dir: {out_dir} \n"
                                 f"odm_list:{web_odm_list}")
            process(web_odm_list)
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, os.path.join(
                script_dir, "downloads"))
            # Process log file for Cronitor
            log_str = process_logfile(LOG_FILENAME, terms=(
                "Downloading", "expired", "generating", "merged"))
            # Send complete event and log to Cronitor
            monitor.ping(state='complete', message=log_str,
                         metrics={'count': len(web_odm_list), 'error_count': error_count})


def main_run():
    # AutoBooks
    logger.info("Started AutoBooks V.{} By:IvyB", version)
    # Try to change to ODM folder
    try:
        os.chdir(odm_dir)
    except FileNotFoundError:
        logger.critical("The provided .odm dir was not found, exiting")
        sys.exit(1)
    else:
        odm_list = glob.glob("*.odm")
        monitor.ping(state='run',
                     message=f"AutoBooks by IvyB v.{version} \n"
                             f"logfile: {LOG_FILENAME}\n odm_dir: {odm_dir} \n out_dir: {out_dir} \n"
                             f"odm_list:{odm_list}")

        # Check if any .odm files exist in odm_dir
        if len(odm_list) == 0:
            monitor.ping(state='fail', message='Error: No .odm files found, exiting',
                         metrics={'error_count': error_count})
            logger.critical("No .odm files found, exiting")
            sys.exit(1)
        else:
            process(odm_list)
            # Cleanup files
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, odm_dir)
            # Send complete event and log to Cronitor
            log_str = process_logfile(LOG_FILENAME, terms=(
                "Downloading", "expired", "generating", "merged", "saved"))
            monitor.ping(state='complete', message=log_str,
                         metrics={'count': len(odm_list), 'error_count': error_count})


if __name__ == "__main__" and config["test_run"] == "True":
    web_run()
