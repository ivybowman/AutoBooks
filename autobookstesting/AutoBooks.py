from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from configparser import ConfigParser
from unittest.mock import patch
from datetime import datetime
from time import sleep
from pathlib import Path
import odmpy.odm as odmpy
from loguru import logger
from utils import InterceptHandler, RedactingFormatter
import pandas as pd
import selenium
import cronitor
import glob
import sys
import shutil
import logging
import os
import requests

# Set Vars
scriptver = "0.2.1"  # Version number of script
error_count = 0
good_odm_list = []
bad_odm_list = []
log_list = []
library_list = []
book_id_list = []
book_title_list = []
book_odm_list = []
scriptdir = os.path.join(Path.home(), "AutoBooks")
csv_path = os.path.join(scriptdir, 'web_known_files.csv')

# Check paths, and if not found do first time setup
if os.path.exists(scriptdir):
    os.chdir(scriptdir)
else:
    os.mkdir(scriptdir)
    main_conf = requests.get('https://raw.githubusercontent.com/ivybowman/AutoBooks/main/autobooks_template.conf')
    odmpy_conf = requests.get("https://raw.githubusercontent.com/ivybowman/AutoBooks/main/odmpydl.conf")
    folders = ['log', 'web_downloads', 'chrome_profile', 'sourcefiles']
    for folder in folders:
        os.mkdir(os.path.join(scriptdir, folder))
    with open(os.path.join(scriptdir, "autobooks.conf"), mode='wb') as localfile:
        localfile.write(main_conf.content)
    with open(os.path.join(scriptdir, "odmpydl.conf"), mode='wb') as localfile:
        localfile.write(odmpy_conf.content)
    print("Finished setup please configure settings in file: ", os.path.join(scriptdir, "autobooks.conf"))
    sys.exit(1)

# Logging Config
LOG_FILENAME = os.path.join(scriptdir, 'log', 'AutoBooks-{:%H-%M-%S_%m-%d-%Y}-Main.log'.format(datetime.now()))
console_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {message}\n{exception}"
file_log_format = "{time:HH:mm:ss A} [{name}:{function}] {level}: {extra[scrubbed]}\n{exception}"
redacting_formatter = RedactingFormatter(patterns=["[34m[1m", "[39m[22m", "[34m[22m", "[35m[22m"], source_fmt=file_log_format)
logger.configure(handlers=[
        {'sink': sys.stderr, "format": console_log_format},
        {'sink': LOG_FILENAME, "format": redacting_formatter.format}
    ])
odmpy.logger.handlers.clear()
odmpy.logger.addHandler(InterceptHandler())

# Read config file
parser = ConfigParser()
parser.read(os.path.join(scriptdir, "autobooks.conf"))
odmdir = parser.get("DEFAULT",
                    "odm_folder")  # Folder that contains the .odm files to process. For windows use / slashes
outdir = parser.get("DEFAULT",
                    "out_folder")  # Folder where the finished audiobooks will be moved to. For windows use / slashes

# Cronitor Setup
cronitor.api_key = parser.get("DEFAULT", "cronitor_apikey")  # Cronitor API key https://cronitor.io/
monitor = cronitor.Monitor(parser.get("DEFAULT", "cronitor_name_main"))  # Set Cronitor monitor name
web_monitor = cronitor.Monitor(parser.get("DEFAULT", "cronitor_name_web"))  # Set Cronitor monitor name


# Function to process the books.
def process_books(odm_list):
    global error_count
    logger.info('Begin processing booklist: {}', " ".join(odm_list))
    for x in odm_list:
        if parser.get('DEFAULT', "test_args") == "true":
            odmpy_args = ["odmpy", "dl", x]
        else:
            odmpy_args = ["odmpy", "dl", "@" + os.path.join(scriptdir, "odmpydl.conf"), x]
        with patch.object(sys, 'argv', odmpy_args):
            try:
                odmpy.run()
            except FileNotFoundError:
                logger.error("Could not find odm file {}", x)
            except FileExistsError:
                logger.error("FileAlreadyExists, likely from m4b creation attempt")
            except SystemExit as e:
                bad_odm_list.append(x)
                try:
                    os.remove("cover.jpg")
                except FileNotFoundError:
                    logger.debug("Could not remove cover.jpg, moving on")
                else:
                    logger.debug("Removed cover.jpg to prep for next attempt")
                error_count += 1
            else:
                good_odm_list.append(x)
    logger.info("Book Processing Finished")


# Function to cleanup in and out files.
def cleanup(m4bs, odms, odmfolder):
    global error_count
    # Move m4b files to outdir
    for x in m4bs:
        exists = os.path.isfile(os.path.join(outdir + x))
        if exists:
            logger.error("Book {} already exists in outdir skipped", x)
            error_count += 1
        else:
            shutil.move(os.path.join(odmfolder, x), os.path.join(outdir, x))
            logger.info("Moved book {} to outdir", x)
    # Backup source files
    sourcefiles = odms + glob.glob("*.license")
    for x in sourcefiles:
        if os.path.isfile(os.path.join(scriptdir, "sourcefiles", x)):
            logger.error("File {} already exists in sourcefiles dir skipped", x)
            error_count += 1
        else:
            shutil.move(x, os.path.join(scriptdir, "sourcefiles", x))
            logger.info("Moved file {} to sourcefiles", x)


# Function for login
def web_login(driver, name, cardno, pin, select):
    global error_count
    logger.info("Logging into library: {}", name)
    # Attempt selecting library from dropdown
    if select != "false":
        select_box = driver.find_element(By.XPATH, '//input[@id="signin-options"]')
        webdriver.ActionChains(driver).move_to_element(select_box).click().send_keys(select).perform()
        sleep(1)
        webdriver.ActionChains(driver).send_keys(Keys.ARROW_DOWN).send_keys(Keys.RETURN).perform()
    # Attempt sending card number
    try:
        driver.find_element(By.ID, "username").send_keys(cardno)
    except selenium.common.exceptions.NoSuchElementException:
        logger.critical("Can't find card number field skipped library {}", )
        error_count += 1
    # Attempt sending pin Note:Some pages don't have pin input
    if pin != "false":
        driver.find_element(By.ID, "password").send_keys(pin)
    driver.find_element(By.CSS_SELECTOR, "button.signin-button.button.secondary").click()
    sleep(5)


# Function to download loans from OverDrive page
def web_dl(driver, df, name):
    global error_count
    #Gather all book title elements and check if any found
    books = driver.find_elements(By.XPATH, '//a[@tabindex="0"][@role="link"]')
    if len(books) == 0:
        logger.warning("Can't find books skipped library: {}", name)
        error_count += 1
        return ()
    else:
        logger.info("Begin DL from library: {} ", name)
        bookcount = 0
        for i in books:
            #Fetch info about the book
            book_url = i.get_attribute('href')
            book_info = i.get_attribute('aria-label')
            book_info_split = book_info.split(". Audiobook. Expires in")
            book_dl_url = book_url.replace('/media/', '/media/download/audiobook-mp3/')
            book_id = int(''.join(filter(str.isdigit, book_url)))
            book_title = book_info_split[0]
            if "Audiobook." in book_info:
                if str(book_id) in df['book_id'].to_string():
                    logger.info('Skipped {} found in known books', book_title)
                else:
                    # Download book
                    driver.get(book_dl_url)
                    logger.info("Downloaded book: {}", book_title)
                    book_odm = max(glob.glob("*.odm"), key=os.path.getmtime)
                    bookcount += 1

                    #Add book data to vars
                    library_list.append(name)
                    book_id_list.append(book_id)
                    book_title_list.append(book_title)
                    book_odm_list.append(book_odm)
            sleep(1)

       
        sleep(1)
        logger.info("Finished downloading {} books from library {}", bookcount, name)
    return ()

def main_run():
    # AutoBooks
    logger.info("Started AutoBooks V.{} By:IvyB", scriptver)
    # Try to change to ODM folder
    try:
        os.chdir(odmdir)
    except FileNotFoundError:
        logger.critical("The provided .odm dir was not found, exiting")
        sys.exit(1)
    else:
        odm_list = glob.glob("*.odm")
        monitor.ping(state='run',
                     message='AutoBooks by IvyB Version:' + scriptver + '\n odmdir:' + odmdir + '\n outdir:' + outdir + '\n logfile:' + LOG_FILENAME + '\n Found the following books \n' + " ".join(
                         odm_list))

        # Check if any .odm files exist in odmdir
        if len(odm_list) == 0:
            monitor.ping(state='fail', message='Error: No .odm files found, exiting',
                         metrics={'error_count': error_count})
            logger.critical("No .odm files found, exiting")
            sys.exit(1)
        else:
            process_books(odm_list)
            # Cleanup input and output files
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, odmdir)
            # Process log file for Cronitor
            with open(LOG_FILENAME) as logs:
                lines = logs.readlines()
                log_list = []
                for line in lines:
                    if any(term in line for term in ("Downloading", "expired", "generating", "merged")):
                        log_list.append(line)
                # Send complete event and log to Cronitor
                monitor.ping(state='complete', message="".join(log_list),
                             metrics={'count': len(odm_list), 'error_count': error_count})


# AutoBooks Web Code
def web_run():
    if len(parser.sections()) == 0:
        logger.critical("No libraries configured!")
        sys.exit(1)
    else:
        logger.info("Started AutoBooks Web V.{} By:IvyB", scriptver)
        monitor.ping(state='run',
                     message='AutoBooks Web by IvyB Version:' + scriptver + '\n logfile:' + LOG_FILENAME + '\n LibraryCount: ' + str(
                         len(parser.sections())))
        # Configure WebDriver options
        options = Options()
        prefs = {
            "download.default_directory": os.path.join(scriptdir, "web_downloads"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_argument('user-data-dir=' + os.path.join(scriptdir, "chrome_profile"))
        # Headless mode check
        if parser.get('DEFAULT', "web_headless") == "true":
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        options.add_experimental_option('prefs', prefs)
        driver = webdriver.Chrome(options=options)

        # Attempt to read known files csv for checking books
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, sep=",")
        else:
           df = pd.DataFrame({
            'book_id': book_id_list,
            })
        os.chdir(os.path.join(scriptdir,"web_downloads"))
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
        odmlist = glob.glob("*.odm")

        # Process log file for Cronitor.
        with open(LOG_FILENAME) as logs:
            lines = logs.readlines()
            log_list = []
            for line in lines:
                if "AutoBooks.web" in line:
                    log_list.append(line)
            monitor.ping(state='complete', message="".join(odmlist),
                         metrics={'count': len(odmlist), 'error_count': error_count})

        # Call Minimum DL functions
        if len(odmlist) != 0:
            logger.info("Started AutoBooks V.{} By:IvyB", scriptver)
            monitor.ping(state='run',
                         message='AutoBooks by IvyB Started from web Version:' + scriptver + '\n outdir:' + outdir + '\n logfile:' + LOG_FILENAME + '\n Found the following books \n' + " ".join(
                             odmlist))
            process_books(odmlist)
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, os.path.join(scriptdir, "web_downloads"))
            # Process log file for Cronitor
            with open(LOG_FILENAME) as logs:
                lines = logs.readlines()
                log_list = []
                for line in lines:
                    if any(term in line for term in ("Downloading", "expired", "generating", "merged")):
                        log_list.append(line)
                # Send complete event and log to Cronitor
                monitor.ping(state='complete', message="".join(log_list),
                             metrics={'count': len(odmlist), 'error_count': error_count})
        #return["\n".join(title_list), error_count]


if __name__ == "__main__" and parser.get('DEFAULT', "test_run") == "true":
    web_run()
