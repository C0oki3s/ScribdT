import sqlite3
import requests
import argparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import signal
import sys
import threading
import queue

def create_db(filename):
    if filename:
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS documents
                     (id INTEGER PRIMARY KEY, reader_url TEXT, author_name TEXT, title TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, img_url TEXT)''')
        conn.commit()
        conn.close()

def insert_document(q, db_file):
    while True:
        item = q.get()
        if item is None:
            break
        reader_url, author_name, title = item
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("INSERT INTO documents (reader_url, author_name, title) VALUES (?, ?, ?)", (reader_url, author_name, title))
        conn.commit()
        conn.close()
        q.task_done()

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

class NoDocumentsFoundError(Exception):
    pass

def fetch_document_page(args, page):
    url = "https://www.scribd.com/search/query"
    params = {"query": args.query, "page": page}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        try:
            data = response.json()
            documents = data.get("results", {}).get("documents", {}).get("content", {}).get("documents", [])
            if documents:
                return documents
            else:
                raise NoDocumentsFoundError
        except requests.exceptions.JSONDecodeError:
            print("Failed to parse JSON response. Here is the raw response text:")
            print(response.text)
    else:
        print(f"Failed to fetch data for page {page}. Status code: {response.status_code}")
        print("Response text:", response.text)
    return []

def fetch_user(user_id):
    base_url = "https://www.scribd.com/user/{}/A"
    url = base_url.format(user_id)
    try:
        response = requests.get(url)
        if response.status_code == 404:
            print(f"User {user_id} not found (404). Skipping.")
            return None
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.title
        title = title_tag.string if title_tag else 'No Title Found'
        username = title.split('|')[0].strip() if title else 'No Title Found'
        img_tags = soup.find_all('img', src=True)
        img_url = None
        for img in img_tags:
            src = img['src']
            if "img/word_user/" in src:
                img_url = src
                break
        return (user_id, username, img_url)
    except requests.RequestException as e:
        print(f"Failed to fetch user {user_id}: {e}")
        return None

def search_documents(args):
    create_db(args.db)
    max_workers = multiprocessing.cpu_count() * 5
    document_queue = queue.Queue()

    threading.Thread(target=insert_document, args=(document_queue, args.db)).start()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_document_page, args, page) for page in range(1, args.pages + 1)]
        for future in as_completed(futures):
            try:
                documents = future.result()
                for doc in documents:
                    reader_url = doc.get("reader_url")
                    author_name = doc.get("author", {}).get("name")
                    title = doc.get("title")
                    print(f"Reader URL: {reader_url}")
                    print(f"Author Name: {author_name}")
                    print(f"Title: {title}")
                    document_queue.put((reader_url, author_name, title))
                    print()
            except NoDocumentsFoundError:
                print("No documents found for the given query. Exiting script.")
            except Exception as e:
                print("An error occurred:", str(e))
    
    document_queue.put(None)  # Signal the end of the queue

def search_users(args):
    create_db(args.db)
    max_workers = multiprocessing.cpu_count() * 5
    user_queue = queue.Queue()

    threading.Thread(target=insert_user, args=(user_queue, args.db)).start()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_user, user_id) for user_id in range(1, args.user_end + 1)]
        for future in as_completed(futures):
            result = future.result()
            if result:
                user_id, username, img_url = result
                if img_url:
                    print(f"User ID: {user_id}")
                    print(f"Username: {username}")
                    print(f"Image URL: {img_url}")
                    user_queue.put((user_id, username, img_url))
    
    user_queue.put(None)  # Signal the end of the queue

def retrieve_data(args):
    conn = sqlite3.connect(args.db)
    c = conn.cursor()
    if args.documents:
        c.execute("SELECT * FROM documents")
        rows = c.fetchall()
        print("Documents:")
        for row in rows:
            print(f" Document_url: {row[1]}\n UserName: {row[2]}\n Title: {row[3]} \n")
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

    # Search in the users table
    c.execute("SELECT * FROM users WHERE username LIKE ?", ('%' + username + '%',))
    user_rows = c.fetchall()


    # Search in the documents table
    c.execute("SELECT * FROM documents WHERE author_name LIKE ?", ('%' + username + '%',))
    document_rows = c.fetchall()

    # Combine the results from both tables
    combined_results = user_rows + document_rows
    if combined_results:
        print("Search Results:")
        for row in combined_results:
            if len(row) == 4:  # Check if it's a user row (4 columns)
                print(f" UserID: {row[1]}\n UserName: {row[2]}\n ImageURL: {row[3]} \n")
            elif len(row) == 5:  # Check if it's a document row (5 columns)
                print(f" DocumentID: {row[0]}\n Reader URL: {row[1]}\n Author Name: {row[2]}\n Title: {row[3]} \n")
    else:
        print("No results found.")

    conn.close()


def signal_handler(sig, frame):
    print("\nUser keyboard interaction detected. Exiting...")
    sys.exit(0)

def main():
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="Search Scribd for documents or users.")
    subparsers = parser.add_subparsers(title='subcommands', dest='subcommand')

    parser_documents = subparsers.add_parser('documents', help='Search for documents')
    parser_documents.add_argument("query", type=str, help="The search query")
    parser_documents.add_argument("-p", "--pages", type=int, default=1, help="Number of pages to search (default: 1)")
    parser_documents.add_argument("--db", default="users.db", type=str, help="SQLite database file to save data")
    parser_documents.set_defaults(func=search_documents)

    parser_users = subparsers.add_parser('users', help='Search for users')
    parser_users.add_argument("-ue", "--user_end", type=int, default=200, help="Number of users to search (default: 200)")
    parser_users.add_argument("--db", default="users.db", type=str, help="SQLite database file to save data")
    parser_users.set_defaults(func=search_users)

    parser_retrieve = subparsers.add_parser('r', help='Retrieve data from SQLite database')
    parser_retrieve.add_argument("-d", "--documents", action="store_true", help="Retrieve documents from the database")
    parser_retrieve.add_argument("--username", type=str, help="Search by username")
    parser_retrieve.add_argument("-u", "--users", action="store_true", help="Retrieve users from the database")
    parser_retrieve.add_argument("--db", type=str, default="users.db", help="SQLite database file to retrieve data from")
    parser_retrieve.set_defaults(func=retrieve_data)

    args = parser.parse_args()

    if args.subcommand == 'r' and args.username:
        search_by_username(args.username, db_file=args.db)
    elif args.subcommand:
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()