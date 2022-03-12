from setuptools import setup

VERSION = '0.4'
DESCRIPTION = 'Python tool to automate processing a batch of OverDrive audiobooks.'
LONG_DESCRIPTION = 'Python tool to automate processing a batch of OverDrive audiobooks.'

# Setting up
setup(
    name="AutoBooks",
    version=VERSION,
    author="Ivy Bowman",
    license="GPL",
    url="https://github.com/ivybowman/AutoBooks",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=["autobooks"],
    entry_points={
        "console_scripts": [
            "autobooks = autobooks.AutoBooks:main_run",
            "autobooks-web = autobooks.AutoBooks:web_run",
            "autobooks-discord = autobooks.AutoBooksDiscord:run"
        ]
    },
    install_requires=["odmpy @ git+https://git@github.com/ping/odmpy.git", "cronitor", "pandas", "discord.py",
                      "requests", "loguru", "lxml"],
    include_package_data=True,
    platforms="any",
    keywords=['python', 'AutoBooks'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ]
)
