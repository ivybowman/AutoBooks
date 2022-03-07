import glob
import os
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
import selenium
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from utils import InterceptHandler, RedactingFormatter, process_logfile

# Set Vars
version = "0.2.1"  # Version number of script
error_count = 0
good_odm_list, bad_odm_list, library_list, book_id_list, book_title_list, book_odm_list = ([
] for i in range(6))
script_dir = os.path.join(Path.home(), "AutoBooks")
csv_path = os.path.join(script_dir, 'web_known_files.csv')

# Check paths, and if not found do first time setup
if os.path.exists(script_dir):
    os.chdir(script_dir)
else:
    os.mkdir(script_dir)
    main_conf = requests.get(
        'https://raw.githubusercontent.com/ivybowman/AutoBooks/main/autobooks_template.conf')
    folders = ['log', 'downloads', 'profile', 'source_backup']
    for folder in folders:
        os.mkdir(os.path.join(script_dir, folder))
    with open(os.path.join(script_dir, "autobooks.conf"), mode='wb') as local_file:
        local_file.write(main_conf.content)
    print("Finished setup please configure settings in file: ",
          os.path.join(script_dir, "autobooks.conf"))
    sys.exit(1)

# Logging Config
LOG_FILENAME = os.path.join(
    script_dir, 'log', 'AutoBooks-{:%H-%M-%S_%m-%d-%Y}.log'.format(datetime.now()))
patterns = ['[34m[1m', '[39m[22m', '[34m[22m', '[35m[22m']
console_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {message}\n{exception}"
cronitor_log_format = "[{name}:{function}] {level}: {message}\n{exception}"
file_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {extra[scrubbed]}\n{exception}"
redacting_formatter = RedactingFormatter(patterns=patterns, source_fmt=file_log_format)
logger.configure(handlers=[
    {'sink': sys.stderr, "format": console_log_format},
    {'sink': LOG_FILENAME, "format": redacting_formatter.format},
    # {'sink': process_logfile(), "format": cronitor_log_format}
])
odmpy.logger.handlers.clear()
odmpy.logger.addHandler(InterceptHandler())

# Read config file
parser = ConfigParser()
parser.read(os.path.join(script_dir, "autobooks.conf"))
odm_dir = parser.get("DEFAULT", "odm_folder")
out_dir = parser.get("DEFAULT", "out_folder")
library_count = len(parser.sections())
# Cronitor Setup https://cronitor.io/
cronitor.api_key = parser.get("DEFAULT", "cronitor_apikey")
monitor = cronitor.Monitor(parser.get("DEFAULT", "cronitor_name_main"))
web_monitor = cronitor.Monitor(parser.get("DEFAULT", "cronitor_name_web"))


# Function to process the books.
def process(odm_list):
    global error_count
    logger.info('Begin processing book list: {}', " ".join(odm_list))
    for x in odm_list:
        if parser.get('DEFAULT', "test_args") == "True":
            odmpy_args = ["odmpy", "dl", "--nobookfolder", x]
        else:
            odmpy_args = ["odmpy", "dl", "-c", "-m", "--mergeformat", "m4b", "--nobookfolder", x]
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


# Function for login
def web_login(driver, name, card_num, pin, select):
    global error_count
    logger.info("Logging into library: {}", name)
    # Attempt selecting library from dropdown
    if select != "False":
        select_box = driver.find_element(
            By.XPATH, '//input[@id="signin-options"]')
        webdriver.ActionChains(driver).move_to_element(
            select_box).click().send_keys(select).perform()
        sleep(1)
        webdriver.ActionChains(driver).send_keys(
            Keys.ARROW_DOWN).send_keys(Keys.RETURN).perform()
    # Attempt sending card number
    try:
        driver.find_element(By.ID, "username").send_keys(card_num)
    except selenium.common.exceptions.NoSuchElementException:
        logger.critical("Can't find card number field skipped library {}", name)
        error_count += 1
    # Attempt sending pin Note:Some pages don't have pin input
    if pin != "False":
        driver.find_element(By.ID, "password").send_keys(pin)
    driver.find_element(
        By.CSS_SELECTOR, "button.signin-button.button.secondary").click()
    sleep(5)


# Function to download loans from OverDrive page
def web_dl(driver, df, name):
    global error_count
    # Gather all book title elements and check if any found
    books = driver.find_elements(By.XPATH, '//a[@tabindex="0"][@role="link"]')
    if len(books) == 0:
        logger.warning("Can't find books skipped library: {}", name)
        error_count += 1
        return ()
    else:
        logger.info("Begin DL from library: {} ", name)
        book_count = 0
        for i in books:
            # Fetch info about the book
            book_url = i.get_attribute('href')
            book_info = i.get_attribute('aria-label')
            book_info_split = book_info.split(". Audiobook. Expires in")
            book_dl_url = book_url.replace(
                '/media/', '/media/download/audiobook-mp3/')
            book_id = int(''.join(filter(str.isdigit, book_url)))
            book_title = book_info_split[0]

            # Check if found book is a not known audiobook
            if "Audiobook." in book_info:
                if str(book_id) in df['book_id'].to_string():
                    logger.info('Skipped {} found in known books', book_title)
                else:
                    # Download book
                    driver.get(book_dl_url)
                    logger.info("Downloaded book: {}", book_title)
                    book_odm = max(glob.glob("*.odm"), key=os.path.getmtime)
                    book_count += 1

                    # Add book data to vars
                    library_list.append(name)
                    book_id_list.append(book_id)
                    book_title_list.append(book_title)
                    book_odm_list.append(book_odm)
            sleep(1)
        sleep(1)
        logger.info("Finished downloading {} books from library {}",
                    book_count, name)
    return ()


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


# AutoBooks Web Code
def web_run():
    if len(parser.sections()) == 0:
        logger.critical("No libraries configured!")
        sys.exit(1)
    else:
        logger.info("Started AutoBooks Web V.{} By:IvyB", version)
        monitor.ping(state='run',
                     message=(f'AutoBooks Web by IvyB V.{version} \n'
                              f'logfile: {LOG_FILENAME} \n LibraryCount: {str(library_count)}'))

        # Configure WebDriver options
        options = Options()
        prefs = {
            "download.default_directory": os.path.join(script_dir, "downloads"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_argument('user-data-dir=' +
                             os.path.join(script_dir, "profile"))
        # Headless mode check
        if parser.get('DEFAULT', "web_headless") == "True":
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        options.add_experimental_option('prefs', prefs)
        driver = webdriver.Chrome(options=options)

        # Attempt to read known files csv for checking books
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, sep=",")
        else:
            # Failing above create an empty df for checking
            df = pd.DataFrame({
                'book_id': book_id_list,
            })
        os.chdir(os.path.join(script_dir, "downloads"))

        # For every library, open site, attempt sign in, and attempt download.
        for i in range(0, len(parser.sections())):
            library_index = 'library_' + str(i)
            library_subdomain = parser.get(library_index, "library_subdomain")
            library_name = parser.get(library_index, "library_name")
            logger.info("Started library {}", library_name)
            url = "https://" + library_subdomain + ".overdrive.com/"
            driver.get(url + "account/loans")
            sleep(3)
            # Check signed in status and either sign in or move on
            if "/account/ozone/sign-in" in driver.current_url:
                web_login(driver, library_name, parser.get(library_index, "card_number"),
                          parser.get(library_index, "card_pin"), parser.get(library_index, "library_select"))
            web_dl(driver, df, library_name)
            sleep(2)
            # Output book data to csv
        df_out = pd.DataFrame({
            'library_name': library_list,
            'book_id': book_id_list,
            'book_title': book_title_list,
            'book_odm': book_odm_list
        })
        if os.path.exists(csv_path):
            df_out.to_csv(csv_path, mode='a', index=False, header=False)
        else:
            df_out.to_csv(csv_path, mode='w', index=False, header=True)
        driver.close()
        logger.info("AutoBooksWeb Complete")
        web_odm_list = glob.glob("*.odm")

        # Process log file for Cronitor.
        process_logfile(LOG_FILENAME, terms=("web", "ERROR"))
        monitor.ping(state='complete', message="".join(web_odm_list),
                     metrics={'count': len(web_odm_list), 'error_count': error_count})

        # Call DL to process odm files from web
        if len(web_odm_list) != 0:
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
        # return["\n".join(title_list), error_count]


if __name__ == "__main__" and parser.get('DEFAULT', "test_run") == "True":
    web_run()
