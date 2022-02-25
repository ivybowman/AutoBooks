# AutoBooks

Python tool to automate processing a batch of OverDrive audiobooks. 

# Important Disclaimer

The intention of this script is solely to automate downloading and converting of loaned OverDrive audiobooks, in order for use with your preferred audiobook player during the loan period.

# Features

- Downloads and converts multiple .odm files to chapterized .m4b audiobook files automatically.
- Moves the outputted audiobooks to a chosen folder.
- Backs up the download files in case you need to redownload the books.
- Logs to console and timestamped logfile.
- Reports execution status and some logs to a [Cronitor](https://cronitor.io/) monitor.

# Requirements

- Tools: python, pip, git, ffmpeg, odmpy
- Accounts: [Cronitor](https://cronitor.io/) For script monitoring

# Links

- [Setup Guides(WorkInProgress)](setup.md)

To configure autobooks browse to the AutoBooks folder located in your home directory or user folder and edit the autobooks.conf file.

# Credits

- [odmpy](https://github.com/ping/odmpy/)
- [StackOverflow](https://stackoverflow.com/) 
- [Cronitor](https://cronitor.io/)
