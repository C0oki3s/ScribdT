
# ScribdT - Focused on Extracting Data from Scribd

## Usage

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

> Querying Documents in Scribd

```bash
python app.py documents query="{query}" --db any.db
```

> User Bruteforce in Scribd

```bash
python app.py users -ue=500 --db any.db
```

> Retrive Saved Data in DB file

 - Users
```bash
python app.py r -u --db any.db
```

 - Documents 
```bash
python app.py r -d --db any.db
```

 - UserName
```bash
python app.py r --username={name} --db any.db
```

