@echo off
cd %userprofile%
mkdir AutoBooks
cd AutoBooks
mkdir log sourcefiles chrome_profile web_downloads
pip3 install git+https://git@github.com/ivybowman/autobooks.git --upgrade --force-reinstall