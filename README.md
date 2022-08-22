
<p align="center">
    <img src="https://raw.githubusercontent.com/ivybowman/AutoBooks/main/img/logo/small_pink.png">
</p>

# Important Disclaimer

The intention of this script is solely to automate downloading and converting of loaned OverDrive audiobooks, only
for personal use with your preferred audiobook player during the loan period.

# Features

- AutoBooks Web: Uses requests to download odm files.
- Uses odmpy to fulfill and convert odm files to m4b audiobooks with chapters.
- Moves the generated audiobooks to a chosen folder.
- Backs up the download files in case you need to re-download the books.
- Logs to console and timestamped logfile.
- Reports execution status and some logs to a [Cronitor](https://cronitor.io/) monitor.
- Can be controlled via included Discord bot or terminal.

# Prerequisites

- Tools: git, ffmpeg, odmpy (Installed in setup guide.)
- Accounts: [Cronitor](https://cronitor.io/) For script monitoring, optional but will display errors if not setup.

# Links

- [Setup Guides](setup.md)

# Usage

- AutoBooks: `autobooks`
- AutoBooks Discord bot: `autobooks-discord`

# Credits & Tools Used

- [odmpy](https://github.com/ping/odmpy/) Simple console manager for OverDrive audiobook loans.
- [Cronitor](https://cronitor.io/) Simple monitoring for any application.
- [Homebrew](https://brew.sh/) Package manager for macOS & Linux.
- [Scoop](https://scoop.sh/) Package manager for Windows.
