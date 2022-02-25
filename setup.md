# AutoBooks

Python tool to automate processing a batch of OverDrive audiobooks.  

# Important Disclaimer

The intention of this script is solely to automate downloading and converting of loaned OverDrive audiobooks, in order for use with your prefered audiobook player during the loan period.

## Windows Setup Guide

### Install Programs

1. Download and install the latest release of git from https://gitforwindows.org/ using the default settings.
2. Download and install the latest release of python from https://www.python.org/downloads/ or the windows store.  
Note: When installing python be sure to select add python to path.  
After installation open Windows Settings > Apps > Apps & features and turn off the two python app installer aliases.
3. Download and install the latest release build of FFmpeg from https://github.com/GyanD/codexffmpeg/releases/ using the guide below

### FFmpeg on Windows Install Guide

1. Extract the ffmpeg zip downloaded above.
2. Rename the folder containing a few subfolders to "ffmpeg".
3. Copy the "ffmpeg" folder to the root of your C drive.
4. Type "path" into windows search and open "Edit the system environment variables".
5. Click "Enviroment Variables" then double click on "Path".
6. On the first blank line type or paste. `C:\ffmpeg\bin`
7. Click Ok on the 3 open windows to save and close.

### Install ODMPY

1. First open a powershell or cmd window, and run the following commands to ensure validity  
`python --version` `pip --version` `git --version` `ffmpeg -version`
2. Open a powershell or cmd window and run `pip install git+https://git@github.com/ping/odmpy.git --upgrade --force-reinstall`
3. Run 

## Debian/Ubuntu Linux Setup Guide

### Install Programs
//TODO

## MacOS Setup Guide

This guide works for both M1 and Intel based Macs.

### Install Programs
1. Run python3 in your terminal and follow prompts to install the xcode command line tools.
2. Setup homebrew using the following command in your terminal. Be sure to follow instructions at the end for adding homebrew to path.
`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
3. Run the following command to install some needed tools. Note: Chromedriver requires Google Chrome to be installed.
`brew install ffmpeg chromedriver`

### AutoBooks Install and Setup
To install the latest version run the following command.
`pip3 install git+https://git@github.com/ivybowman/autobooks.git --upgrade --force-reinstall`
To uninstall AutoBooks run the following command.
`pip3 uninstall autobooks`


## AutoBooks Configuration

Open the `autobooks.conf` file located in your user folder in a text editor. The options are explained below
``` json
[DEFAULT]
cronitor_name_main = AutoBooks #Name of monitor to use for Cronitor in the processing function
cronitor_name_web = AutoBooksWeb #Name of monitor to use for Cronitor in the web function.
cronitor_apikey = #Apikey for Cronitor to send monitoring data.
discord_bot_token = #Optional for using the discord bot functionality.
odm_folder = #Folder where your .odm files are located
out_folder = 

#To add more libraries just make a copy of the below section and increment the number. 
[library_0]
library_page = #Overdrive subdomain of your library. Ex: "examplepage" from "https://examplepage.overdrive.com/"
library_select = false #If your library uses a dropdown box on the sign in put the exact text here. If not put "false" Ex: "Example County Library"
card_number = #Supply library card number here
card_pin = #Supply library card pin here. If not used for sign in put "false"
```


# Credits

- [odmpy by Ping](https://github.com/ping/odmpy/)
- [StackOverflow](https://stackoverflow.com/) 
- [Cronitor](https://cronitor.io/)