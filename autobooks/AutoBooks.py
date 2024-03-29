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

from autobooks.utils import InterceptHandler, RedactingFormatter, process_logfile, parse_form, craft_booklist, \
    query_login_form

# Set Vars
version = "1.2"  # Version number of script
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
    with open(os.path.join(script_dir, "autobooks.ini"), mode='wb') as local_file:
        local_file.write(main_conf.content)
    print("Finished setup please configure settings in file: ",
          os.path.join(script_dir, "autobooks.ini"))
    sys.exit(1)

# Logging Config
LOG_PATH = os.path.join(script_dir, 'log')
LOG_FILENAME = os.path.join(
    script_dir, 'log', 'AutoBooks-{:%H-%M-%S_%m-%d}.log'.format(datetime.now()))

patterns = ['[34m[1m', '[39m[22m', '[34m[22m', '[35m[22m']  # Used to remove color codes.
console_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {message}\n{exception}"
cronitor_log_format = "[{name}:{function}] {level}: {message}\n{exception}"
file_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {extra[scrubbed]}\n{exception}"
redacting_formatter = RedactingFormatter(patterns=patterns, source_fmt=file_log_format)
logger.configure(handlers=[
    {'sink': sys.stderr, "format": console_log_format, 'level': 'DEBUG'},
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


# Function to process the odm files into books.
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


# Function to authenticate with Overdrive
def login(library):
    login_session = requests.Session()
    logger.info("Logging into: {}", library["subdomain"])
    box = login_session.get(f'https://{library["subdomain"]}.overdrive.com/account/ozone/sign-in?forward=%2F')
    # logger.success('Fetched login page. Status Code: {}', box.status_code)
    form_list = parse_form(box, "loginForms")['forms']
    login_form = query_login_form(form_list, library['select_box'])
    sleep(0.5)
    auth = login_session.post(f'https://{library["subdomain"]}.overdrive.com/account/signInOzone',
                              params=(('forwardUrl', '/'),),
                              data={
                                  'ilsName': login_form['ilsName'],
                                  'authType': login_form['type'],
                                  'libraryName': login_form['displayName'],
                                  'username': library['card_number'],
                                  'password': library['card_pin']
                              })
    logger.success("Logged into: {} Status Code: {} ", library["subdomain"], auth.status_code)
    # print("AUTH URL: ", auth.url)
    base_url = auth.url
    if not base_url.endswith('/'):
        base_url = base_url + '/'
    return base_url, login_form['ilsName'], login_session


# Function to download loans from OverDrive page
def download(df, session, base_url, name, book_list):
    global error_count
    df_out = pd.DataFrame()
    logger.info("Begin DL from library: {} ", name)
    odm_list = []
    book_count = 0
    if len(book_list) == 0:
        logger.info("Can't find any new audiobooks skipped library: {}", name)
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
                book_count += 1
                # print(odm_filename)
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
def run():
    global error_count
    web_odm_list = []
    if len(parser.sections()) == 0:
        logger.critical("No libraries configured!")
        sys.exit(1)
    else:
        logger.info("Started AutoBooks Web V.{} By:IvyB on Host: {}", version, platform.node())
        monitor.ping(state='run',
                     message=(f'AutoBooks Web by IvyB V.{version} on Host: {platform.node()} \n'
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
            logger.info("Begin Processing library: {}", lib_conf['name'])
            sleep(0.5)
            base_url, ils_name, session = login(lib_conf)

            loans = session.get(f'{base_url}account/loans')
            sleep(0.5)
            if loans.status_code == 200:
                book_list = craft_booklist(loans)
                if len(book_list) != 0:
                    df_out, odm_list = download(df, session, base_url, ils_name, book_list)
                    sleep(0.5)
                    if web_odm_list == [] and odm_list != []:
                        web_odm_list = odm_list
                    else:
                        web_odm_list.extend(odm_list)
                    sleep(2)
                    # Write book data to csv
                    if os.path.isfile(csv_path):
                        df_out.to_csv(csv_path, mode='a', index=False, header=False)
                    else:
                        df_out.to_csv(csv_path, mode='w', index=False, header=True)
                else:
                    logger.warning("Can't find books skipped library: {}", lib_conf['name'])
                    error_count += 1
            session.close()
        logger.info("Download Complete")

        # Process log file for Cronitor.
        web_log = process_logfile(LOG_FILENAME, terms=("web", "ERROR"))
        monitor.ping(state='complete',
                     message=f'{"".join(web_log)}',
                     metrics={'count': len(web_odm_list), 'error_count': error_count})

        # Process odm files from web
        if len(web_odm_list) != 0:
            logger.info("Started Downloading Books")
            monitor.ping(state='run',
                         message=f"Started Processing Books \n"
                                 f"logfile: {LOG_FILENAME}\n out_dir: {config['out_folder']} \n"
                                 f"odm_list:{web_odm_list}")
            good_odm_list, bad_odm_list = process(web_odm_list)
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, os.path.join(
                script_dir, "downloads"))
            # Process log file for Cronitor
            log_str = process_logfile(LOG_FILENAME, terms=(
                "Downloading", "expired", "generating", "merged"))
            # Send complete event and log to Cronitor
            monitor.ping(state='complete', message=log_str,
                         metrics={'count': len(web_odm_list), 'error_count': error_count})


if __name__ == "__main__" and config["test_run"] == "True":
    run()
