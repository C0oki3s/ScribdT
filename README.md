# ScribdT - Focused on Extracting Data from Scribd

## Overview
ScribdT is a powerful tool designed to search for documents or users on Scribd and extract specific data based on given queries. It provides functionalities to perform user brute force searches and retrieve user data from a SQLite database.

## Table of Contents
1. [Installation](#installation)
2. [Usage](#usage)
3. [Subcommands](#subcommands)
    - [Querying Documents](#querying-documents)
    - [User Bruteforce](#user-bruteforce)
    - [Retrieve Saved Data](#retrieve-saved-data)
4. [Upgrading the Package](#upgrading-the-package)

## Installation
To install ScribdT, you need to clone the repository and install the package using `setup.py`.

```bash Linux
git clone <repository-url>
cd ScribdT
pip install .
```

```bash Windows
git clone <repository-url>
cd ScribdT
py -3.12 -m venv venv
pip install .
python -m spacy download en_core_web_lg
```

## Usage

To use ScribdT, run the ScribdTool command with the appropriate subcommand and options. The general usage format is:

```bash
ScribdT [-h] {documents,users,r} ...
```

## Subcommands

```bash
usage: app.py [-h] {documents,users,r} ...

Search Scribd for documents or users.
options:
  -h, --help           show this help message and exit

subcommands:
  {documents,users,r}
    documents          Search for documents
    users              Search for users
    r                  Retrieve data from SQLite database
```

## Querying Documents

To search for documents on Scribd, use the documents subcommand. The general format is:

#### Example
```bash
ScribdT documents query="passport" --filters filters.json --cookies cookies.txt --document-format auto
```
This command searches Scribd for documents related to "passport", reads the best available text from TXT/PDF/DOCX responses, then runs regex validators, GLiNER, Presidio, and secret scanning before merging confidence scores.

--document-format:

- Optional argument. Use `auto`, `txt`, `pdf`, or `docx`. The default is `auto`.

--filters filters.json / --detectors:

- Optional argument. Configures detectors, entities, GLiNER labels, Presidio context, allow-list, and exclusion rules.

- Useful for OSINT triage because users can keep the default `regex,gliner,presidio,secrets` pipeline or customize detectors with `--detectors` or the JSON config.

> The filters.json file might contain parameters like:

```json
{
  "detectors": ["regex", "gliner", "presidio", "secrets"],
  "entities": ["PERSON", "FIRST_NAME", "LAST_NAME", "PASSWORD_CANDIDATE", "EMAIL_ADDRESS"],
  "score_threshold": 0.5,
  "context": ["passport", "phone", "email", "id", "password"],
  "gliner_labels": ["person", "first name", "last name", "username", "password", "api key"],
  "allow_list": [],
  "exclude_terms": [],
  "exclude_regex": []
}
```

--cookies cookies.txt:
* Supplies a cookies file used to authenticate with Scribd.

* _scribd_session=yourCookies It can be anywhere as we have --cookies flag


### User Bruteforce

To search for users on Scribd, use the `users` subcommand. The general format is:

#### Examples
```bash
ScribdT users -ue=500 --db scribd_users.db
ScribdT users --user-id 123456 --db scribd_users.db
ScribdT users --user-start 100000 --user-end 101000 --db scribd_users.db
```
The first command searches IDs 1 through 500. The second targets one known user ID. The third searches a specific ID range.

## Retrieve Saved Data

To retrieve data from a SQLite database, use the r subcommand. ScribdT supports retrieving users and searching by username.

```bash
ScribdT r -u --db DATABASE_FILE
```
This command retrieves all users from the specified SQLite database file.

## Retrieve by Username

```bash
ScribdT r --username=johndoe --db scribd_users.db
```
This command retrieves information about the user with the username "johndoe" from the specified SQLite database file.

## Upgrading the Package

```bash
pip install --upgrade .
```


If you appreciate my efforts, I would greatly appreciate your support. Your encouragement keeps me motivated to explore more in cybersecurity and continue developing open-source tools. Thank you for your support!

<a href="https://buymeacoffee.com/c0oki3s" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
