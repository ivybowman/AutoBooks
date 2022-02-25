# AutoBooks

Python tool to automate processing a batch of OverDrive audiobooks. 

# Important Disclaimer

The intention of this script is solely to automate downloading and converting of loaned OverDrive audiobooks, in order for use with your preferred audiobook player during the loan period.

# Features

- Uses selenium and chromedriver to download the odms from overdrive without user interaction. 
- Uses odmpy to fulfill and convert odms to chapterized m4b audiobook files.
- Moves the generated audiobooks to a chosen folder.
- Backs up the download files in case you need to redownload the books.
- Logs to console and timestamped logfile.
- Reports execution status and some logs to a [Cronitor](https://cronitor.io/) monitor.
- Can be controlled via Discord bot or console.

# Prerequisites

- Tools: git, ffmpeg, odmpy, chromedriver (Installed in setup guide.)
- Accounts: [Cronitor](https://cronitor.io/) For script monitoring, optional but will display errors if not setup.

# Links

- [Setup Guides(WorkInProgress)](setup.md)

# Usage

- Run AutoBooks dl/fulfill: `autobooks`
- Run AutoBooks Web: `autobooks-web`
- Run the AutoBooks Discord bot: `autobooks-discord`

# Credits

- [odmpy](https://github.com/ping/odmpy/)
- [StackOverflow](https://stackoverflow.com/) 
- [Cronitor](https://cronitor.io/)
