from configparser import ConfigParser
from unittest.mock import patch
from datetime import datetime
from odmpy.__main__ import main as odmpy
import odmpy.odm as odmpy_log
import logging
import logging.config
import os
import cronitor
import glob
import sys
import shutil

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


#Set initial variables  
scriptdir = os.getcwd() #Store CWD for later copy commands 
scriptver = "1.0" #Version number of script
errorcount = 0
goododms = []
badodms = []

#Logging Config
LOG_FILENAME = os.path.join(scriptdir,'log','AutoBooks-{:%H-%M-%S_%m-%d-%Y}.log'.format(datetime.now()))
fh = logging.FileHandler(LOG_FILENAME)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%I:%M:%S %p',
    handlers=[
        fh,
        logging.StreamHandler(sys.stdout)
    ]) 
fh.setFormatter(RedactingFormatter(fh.formatter, patterns=["[34m[1m","[39m[22m", "[34m[22m"]))
odmpy_log.logger = logging.getLogger('AutoBooks.odmpy')
autobooks_log = logging.getLogger("AutoBooks.main")

#Read config file
parser = ConfigParser()
parser.read("autobooks.conf")
#Cronitor Setup
cronitor.api_key = parser.get("DEFAULT","cronitor_apikey") #Cronitor API key https://cronitor.io/
monitor = cronitor.Monitor(parser.get("DEFAULT","cronitor_name_main")) # Set Cronitor monitor name
#Directory Var's
odmdir= parser.get("DEFAULT","odmdir") #Folder that contains the .odm files to process. For windows use / slashes
outdir= parser.get("DEFAULT","outdir") #Folder where the finished audiobooks will be moved to. For windows use / slashes

#Function to process the books.
def process_books():
    global errorcount
    global goododms
    global badodms
    autobooks_log.info('Begin processing booklist: %s', odmstr)
    for x in odmlist:
        odmpy_args = ["odmpy", "dl", "@" + os.path.join(scriptdir, "odmpydl.conf "), x]
        with patch.object(sys, 'argv', odmpy_args):
            try:
                odmpy()
            except FileNotFoundError:
                autobooks_log.error("Could not find odm file %s", x)
            except FileExistsError:
                autobooks_log.error("FileAlreadyExists, likely from m4b creation attempt")
            except SystemExit as e:
                if e.code == 2:
                    autobooks_log.error("Invalid Arguments")
                elif e.code == 1:
                    badodms.append(x)
                    try: 
                        os.remove("cover.jpg")   
                    except FileNotFoundError: 
                        autobooks_log.debug("Could not remove cover.jpg, moving on")
                    else: 
                        autobooks_log.debug("Removed cover.jpg to prep for next attempt")
                errorcount += 1
            else:
                goododms.append(x)
    autobooks_log.info("Book Processing Finished")
                
#Function to cleanup in and out files. 
def cleanup(m4bs, odms):
    #Move m4b files to outdir
    global errorcount
    global autobooks_log
    for x in m4bs:
        exists = os.path.isfile(outdir + "/" + x)
        if exists: 
            autobooks_log.error("Book %s already exists in outdir skipped", x) 
            errorcount += 1
        else:
            shutil.move(odmdir + "/" + x, outdir + "/")
            autobooks_log.info("Moved book %s to outdir", x)
    #Backup sourcefiles 
    sourcefiles = odms + glob.glob("*.license")
    for x in sourcefiles:
        if os.path.isfile(scriptdir + "/sourcefiles/"+x):
            autobooks_log.error("File %s already exists in sourcefiles dir skipped", x) 
            errorcount += 1
        else:
            shutil.move(x, scriptdir + "/sourcefiles/"+ x)
            autobooks_log.info("Moved file %s to /sourcefiles/", x)


#Start of Script
autobooks_log.info("Started AutoBooks V.%s By:IvyB", scriptver)
#Try to change to ODM folder
try:
    os.chdir(odmdir)
except FileNotFoundError:
    autobooks_log.critical("The provided .odm dir was not found, exiting")
    sys.exit(1)
else:
    odmlist = glob.glob("*.odm")
    odmstr = "".join(odmlist)
    monitor.ping(state='run', message='AutoBooks by IvyB Version:'+scriptver+'\n odmdir:'+odmdir+'\n outdir:'+outdir+'\n logfile:'+LOG_FILENAME+'\n Found the following books \n'+odmstr)

    #Check if any .odm files exist in odmdir
    if len(odmlist) == 0:
        monitor.ping(state='fail', message='Error: No .odm files found, exiting',metrics={'error_count': errorcount})
        autobooks_log.critical("No .odm files found, exiting")
        sys.exit(1)
    else:
        process_books()
        #Cleanup input and output files
        m4blist = glob.glob("*.m4b")
        cleanup(m4blist, goododms)
        #Process log file for Cronitor
        with open(LOG_FILENAME) as logs:
            lines = logs.readlines()
            loglist = []
            for line in lines:
                if any(term in line for term in ("Downloading", "expired", "generating", "merged")):
                    loglist.append(line)
            
            logstr = "".join(loglist)
            #Send complete event and log to Cronitor
            monitor.ping(state='complete', message=logstr, metrics={'count': len(odmlist),'error_count': errorcount})