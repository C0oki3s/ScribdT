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

```bash
git clone <repository-url>
cd ScribdT
pip install .
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
ScribdT documents query="fucking warehouse" --filters filters.json --cookies cookies.txt
```
This command searches Scribd for documents related to "fucking warehouse" and uses the provided filters and cookies.

> filters is a optional Tag as it uses to detect parameters for presidio-analyzer.


### User Bruteforce

To search for users on Scribd, use the `users` subcommand. The general format is:

#### Example
```bash
ScribdT users -ue=500 --db scribd_users.db
```
This command performs a brute force search for up to 500 users on Scribd and saves the results to scribd_users.db.

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






