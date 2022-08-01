# AutoBooks

Python tools to automate processing a batch of OverDrive audiobooks.  

# Important Disclaimer

The intention of this script is solely to automate downloading and converting of loaned OverDrive audiobooks, in order for use with your preferred audiobook player during the loan period.

## Windows Setup Guide

Open a PowerShell window then follow the steps below.
1. Set execution policy to allow the Scoop installer to run.  
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
2. Run the Scoop installer, this is a package manager used to install some prerequisites.  
`iwr -useb get.scoop.sh | iex`
3. Install prerequisites.
`scoop install ffmpeg git`

## macOS Setup Guide

Open a terminal window then follow the steps below. Works with both M1 and Intel Macs.
1. Run python3 in your terminal and follow prompts to install the xcode command line tools.
2. Install Homebrew. Be sure to follow instructions at the end for adding it to path.  
`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
3. Install prerequisites. On trying to use these tools you might see an unidentified developer pop up, this is normal just open the folder and ctrl+click or right-click on the file and click open.
`brew install ffmpeg`

## Debian/Ubuntu Linux Setup Guide

Open a terminal window then follow the steps below. 
2. Update package list.  
`sudo apt-get update`
2. Install prerequisites.  
`sudo apt-get install -y ffmpeg git`


## AutoBooks Install & Setup (All Operating Systems)

### Installation 
To install from the latest source run the following command.  
`pip3 install git+https://git@github.com/ivybowman/autobooks.git --upgrade --force-reinstall`
To install from a specific version run the following command.
`pip3 install git+https://git@github.com/ivybowman/autobooks.git@<VERSION> --upgrade`
To uninstall AutoBooks run the following command.  
`pip3 uninstall autobooks`

### Configuration

1. Open a terminal and run `autobooks` this will run setup commands to create the data folder.
2. Edit the `autobooks.ini` file using one of the commands below or by browsing to the autobooks folder inside your home directory.
- Windows(GUI) PowerShell: `notepad $env:USERPROFILE\AutoBooks\autobooks.ini`
- Windows(GUI) Command Prompt: `notepad %userprofile%\AutoBooks\autobooks.ini`
- macOS(GUI) Terminal: `open -a TextEdit ~/AutoBooks/autobooks.ini`
- Linux or macOS(CLI): `nano ~/AutoBooks/autobooks.ini`


