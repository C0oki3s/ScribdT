import sqlite3

class NoDocumentsFoundError(Exception):
    pass

def create_db(filename):
    if filename:
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, img_url TEXT)''')
        conn.commit()
        conn.close()

def insert_user(q, db_file):
    while True:
        item = q.get()
        if item is None:
            break
        user_id, username, img_url = item
        conn = sqlite3.connect(db_file)
        try:
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, username, img_url) VALUES (?, ?, ?)", (user_id, username, img_url))
            conn.commit()
        except sqlite3.Error as e:
            print("Error inserting user:", e)
        finally:
            conn.close()
            q.task_done()

def retrieve_data(args):
    conn = sqlite3.connect(args.db)
    c = conn.cursor()
    if args.documents:
        print("No document retrieval functionality.")
    elif args.users:
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        print("Users:")
        for row in rows:
            print(f" UserID: {row[1]}\n UserName: {row[2]}\n ImageURL: {row[3]} \n")
    conn.close()

def search_by_username(username, db_file):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username LIKE ?", ('%' + username + '%',))
    user_rows = c.fetchall()

    if user_rows:
        print("Search Results:")
        for row in user_rows:
            print(f" UserID: {row[1]}\n UserName: {row[2]}\n ImageURL: {row[3]} \n")
    else:
        print("No results found in users table.")

    conn.close()

