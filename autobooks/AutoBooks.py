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
import pandas as pd
import selenium
import cronitor
import glob
import sys
import shutil
import logging
import os
import requests

#Logging Redacting formatter from https://relaxdiego.com/2014/07/logging-in-python.html#configuring-your-loggers
class RedactingFormatter(object):
    def __init__(self, orig_formatter, patterns):
        self.orig_formatter = orig_formatter
        self._patterns = patterns

    def format(self, record):
        msg = self.orig_formatter.format(record)
        for pattern in self._patterns:
            msg = msg.replace(pattern, "")
        return msg
        
    def __getattr__(self, attr):
        return getattr(self.orig_formatter, attr)

#Set Vars needed for config
scriptver = "0.2.0" #Version number of script
error_count = 0
good_odm_list=[]
bad_odm_list=[]
scriptdir = os.path.join(Path.home(), "AutoBooks")
csv_path=os.path.join(scriptdir, 'web_known_files.csv')

#Check paths, and if not found do first time setup
if os.path.exists(scriptdir):
    os.chdir(scriptdir)
else:
    os.mkdir(scriptdir)
    main_conf = requests.get('https://raw.githubusercontent.com/ivybowman/AutoBooks/main/autobooks_template.conf')
    odmpy_conf = requests.get("https://raw.githubusercontent.com/ivybowman/AutoBooks/main/odmpydl.conf")
    folders = ['log','web_downloads','chrome_profile', 'sourcefiles']
    for folder in folders:
        os.mkdir(os.path.join(scriptdir, folder))
    with open(os.path.join(scriptdir, "autobooks.conf"), mode='wb') as localfile:    
        localfile.write(main_conf.content)
    with open(os.path.join(scriptdir, "odmpydl.conf"), mode='wb') as localfile:    
        localfile.write(odmpy_conf.content)
    print("Finished setup please configure settings in file: ", os.path.join(scriptdir, "autobooks.conf"))
    sys.exit(1)

#Logging Config
LOG_FILENAME = os.path.join(scriptdir,'log','AutoBooks-{:%H-%M-%S_%m-%d-%Y}-Main.log'.format(datetime.now()))
fh = logging.FileHandler(LOG_FILENAME)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%I:%M:%S %p',
    handlers=[
        fh,
        logging.StreamHandler(sys.stdout)
    ]) 
fh.setFormatter(RedactingFormatter(fh.formatter, patterns=["[34m[1m","[39m[22m", "[34m[22m", "[35m[22m"]))
odmpy.logger = logging.getLogger('AutoBooks.odmpy')
process_logger = logging.getLogger("AutoBooks.main")
web_logger = logging.getLogger("AutoBooks.web")
discord_logger = logging.getLogger("AutoBooks.discord")

#Read config file
parser = ConfigParser()
parser.read(os.path.join(scriptdir, "autobooks.conf"))
odmdir= parser.get("DEFAULT","odm_folder") #Folder that contains the .odm files to process. For windows use / slashes
outdir= parser.get("DEFAULT","out_folder") #Folder where the finished audiobooks will be moved to. For windows use / slashes

#Cronitor Setup
cronitor.api_key = parser.get("DEFAULT","cronitor_apikey") #Cronitor API key https://cronitor.io/
monitor = cronitor.Monitor(parser.get("DEFAULT","cronitor_name_main")) # Set Cronitor monitor name
web_monitor = cronitor.Monitor(parser.get("DEFAULT","cronitor_name_web")) # Set Cronitor monitor name

#Function to process the books.
def process_books(odm_list):
    global error_count
    process_logger.info('Begin processing booklist: %s', " ".join(odm_list))
    for x in odm_list:
        odmpy_args = ["odmpy", "dl", x]
        #odmpy_args = ["odmpy", "dl", "@" + os.path.join(scriptdir, "odmpydl.conf"), x]
        with patch.object(sys, 'argv', odmpy_args):
            try:
                odmpy.run()
            except FileNotFoundError:
                process_logger.error("Could not find odm file %s", x)
            except FileExistsError:
                process_logger.error("FileAlreadyExists, likely from m4b creation attempt")
            except SystemExit as e:
                if e.code == 2:
                    process_logger.error("Invalid Arguments")
                elif e.code == 1:
                    bad_odm_list.append(x)
                    try: 
                        os.remove("cover.jpg")   
                    except FileNotFoundError: 
                        process_logger.debug("Could not remove cover.jpg, moving on")
                    else: 
                        process_logger.debug("Removed cover.jpg to prep for next attempt")
                error_count += 1
            else:
                good_odm_list.append(x)
    process_logger.info("Book Processing Finished")       
#Function to cleanup in and out files. 
def cleanup(m4bs, odms, odmfolder):
    global error_count
    #Move m4b files to outdir
    for x in m4bs:
        exists = os.path.isfile(os.path.join(outdir + x))
        if exists: 
            process_logger.error("Book %s already exists in outdir skipped", x) 
            error_count += 1
        else:
            shutil.move(os.path.join(odmfolder, x), os.path.join(outdir, x))
            process_logger.info("Moved book %s to outdir", x)
    #Backup sourcefiles 
    sourcefiles = odms + glob.glob("*.license")
    for x in sourcefiles:
        if os.path.isfile(os.path.join(scriptdir,"sourcefiles", x)):
            process_logger.error("File %s already exists in sourcefiles dir skipped", x) 
            error_count += 1
        else:
            shutil.move(x, os.path.join(scriptdir, "sourcefiles", x))
            process_logger.info("Moved file %s to sourcefiles", x)

#Function for sign in
def sign_in(driver, name, cardno, pin, select):
    global error_count
    web_logger.info("sign_in: Signing into library %s with card: %s",name,cardno)
    #Attempt select library from dropdown
    if select != "false":
        select_box = driver.find_element(By.XPATH, '//input[@id="signin-options"]')
        webdriver.ActionChains(driver).move_to_element(select_box).click().send_keys(select).perform()
        sleep(1)
        webdriver.ActionChains(driver).send_keys(Keys.ARROW_DOWN).send_keys(Keys.RETURN).perform()
    #Attempt sending card number
    try:
        driver.find_element(By.ID, "username").send_keys(cardno)
    except selenium.common.exceptions.NoSuchElementException:
        web_logger.critical("sign_in: Can't find card number field skipped library %s", )
        error_count += 1
    #Attempt sending pin Note:Some pages don't have pin input
    if pin != "false":
        try:
            driver.find_element(By.ID, "password").send_keys(pin)
        except selenium.common.exceptions.NoSuchElementException:
            web_logger.info("sign_in: Pin field not found")
    driver.find_element(By.CSS_SELECTOR, "button.signin-button.button.secondary").click()
    web_logger.info("sign_in: Signed into library %s",name)
    sleep(5)

#Function to download loans from OverDrive page
def download_loans(driver, df, name):
    global error_count
    library_list=[]
    id_list=[]
    title_list=[]
    books = driver.find_elements(By.XPATH , '//a[@tabindex="0"][@role="link"]')
    #Check if download buttons where found
    if len(books) == 0:
        web_logger.warning("Can't find download button skipped library %s", name)
        error_count += 1
        return()
    else:
        web_logger.info("download_loans: Begin downloading from library %s", name)
        bookcount = 0
        for i in books:
            book_title = format(i.get_attribute('innerHTML'))
            book_url = i.get_attribute('href') 
            book_info = i.get_attribute('aria-label')
            book_dl_url = book_url.replace('/media/', '/media/download/audiobook-mp3/')
            book_id = int(''.join(filter(str.isdigit, book_url)))
            if "eBook." in book_info:
                pass
            else:
                try: 
                    df.query(f"book_id == {book_id}")
                    web_logger.info('download_loans: Skipped %s found in known books',str.strip(book_title))
                except (NameError, AttributeError):
                    library_list.append(name)
                    id_list.append(book_id)
                    title_list.append(book_info)
                    #Download book
                    driver.get(book_dl_url)
                    web_logger.info("download_loans: Downloaded book: %s", str.strip(book_title))
                    bookcount += 1
            sleep(1)

        #Output book data to csv            
        df_out = pd.DataFrame({
        'library_name': library_list,
        'book_id': id_list,
        'audiobook_info': title_list
        })
        if os.path.exists(csv_path):
            df_out.to_csv(csv_path, mode='a', index=False, header=False)
        else:
            df_out.to_csv(csv_path, mode='w', index=False, header=True)
        sleep(1)
        web_logger.info("download_loans: Finished downloading %s books from library %s", bookcount, name)
    return()


def main_run():
    #AutoBooks
    process_logger.info("Started AutoBooks V.%s By:IvyB", scriptver)
    #Try to change to ODM folder
    try:
        os.chdir(odmdir)
    except FileNotFoundError:
        process_logger.critical("The provided .odm dir was not found, exiting")
        sys.exit(1)
    else:
        odm_list = glob.glob("*.odm")
        monitor.ping(state='run', message='AutoBooks DL by IvyB Version:'+scriptver+'\n odmdir:'+odmdir+'\n outdir:'+outdir+'\n logfile:'+LOG_FILENAME+'\n Found the following books \n'+" ".join(odm_list))

        #Check if any .odm files exist in odmdir
        if len(odm_list) == 0:
            monitor.ping(state='fail', message='Error: No .odm files found, exiting',metrics={'error_count': error_count})
            process_logger.critical("No .odm files found, exiting")
            sys.exit(1)
        else:
            process_books(odm_list)
            #Cleanup input and output files
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, odmdir)
            #Process log file for Cronitor
            with open(LOG_FILENAME) as logs:
                lines = logs.readlines()
                log_list = []
                for line in lines:
                    if any(term in line for term in ("Downloading", "expired", "generating", "merged")):
                        log_list.append(line)
                #Send complete event and log to Cronitor
                monitor.ping(state='complete', message="".join(log_list), metrics={'count': len(odm_list),'error_count': error_count})


#AutoBooks Web Code
def web_run():
    if len(parser.sections()) == 0:
        web_logger.critical("No libraries configured!")
        sys.exit(1)
    else:
        web_logger.info("Started AutoBooks Web V.%s By:IvyB", scriptver)
        monitor.ping(state='run', message='AutoBooks Web by IvyB Version:'+scriptver+'\n logfile:'+LOG_FILENAME+'\n LibraryCount: '+str(len(parser.sections())))
        #Configure WebDriver options
        options = Options()
        prefs = {
        "download.default_directory": os.path.join(scriptdir, "web_downloads"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True
        }
        options.add_argument('user-data-dir=' + os.path.join(scriptdir, "chrome_profile"))
        options.add_experimental_option('prefs', prefs)
        driver = webdriver.Chrome(options=options)

        #Attempt to read known files csv for checking books
        try:
            df = pd.read_csv(csv_path, sep=",")
        except FileNotFoundError:
            df = False

        os.chdir("web_downloads")
        #For every library, open site, attempt sign in, and attempt download.
        for i in range(0, len(parser.sections())):
            library_page = parser.get('library_'+str(i), "library_page") 
            web_logger.info("Started library %s", library_page)
            url = "https://" + library_page + ".overdrive.com/"
            driver.get(url+"account/loans")
            sleep(3)
            #Check signed in status and either sign in or move on
            if "/account/ozone/sign-in" in driver.current_url:
                sign_in(driver, library_page, parser.get('library_'+str(i), "card_number"), parser.get('library_'+str(i), "card_pin"), parser.get('library_'+str(i), "library_select"))
            download_loans(driver, df, library_page)
            sleep(2)
        driver.close()
        web_logger.info("AutoBooksWeb Complete")
        odmlist = glob.glob("*.odm")
        #Process log file for web lines.
        with open(LOG_FILENAME) as logs:
            lines = logs.readlines()
            log_list = []
            for line in lines:
                if "AutoBooks.web" in line:
                    log_list.append(line)
            monitor.ping(state='complete', message="".join(odmlist), metrics={'count': len(odmlist),'error_count': error_count})

        #Call Minimum DL functions
        if len(odmlist) != 0:
            process_logger.info("Started AutoBooks DL from web V.%s By:IvyB", scriptver)
            monitor.ping(state='run', message='AutoBooks DL by IvyB Started from web Version:'+scriptver+'\n outdir:'+outdir+'\n logfile:'+LOG_FILENAME+'\n Found the following books \n'+" ".join(odmlist))
            process_books(odmlist)
            m4blist = glob.glob("*.m4b")
            cleanup(m4blist, good_odm_list, os.path.join(scriptdir, "web_downloads"))
            #Process log file for Cronitor
            with open(LOG_FILENAME) as logs:
                lines = logs.readlines()
                log_list = []
                for line in lines:
                    if any(term in line for term in ("Downloading", "expired", "generating", "merged")):
                        log_list.append(line)
                #Send complete event and log to Cronitor
                monitor.ping(state='complete', message="".join(log_list), metrics={'count': len(odmlist),'error_count': error_count})
web_run()