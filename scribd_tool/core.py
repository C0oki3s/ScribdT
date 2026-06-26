import argparse
import multiprocessing
import os
import queue
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from .db import create_db, insert_user, retrieve_data, search_by_username, NoDocumentsFoundError


def read_cookies_from_file(file_path):
    cookies_dict = {}
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            cookies_str = file.read().strip()
        for cookie in cookies_str.split(";"):
            if "=" in cookie:
                name, value = cookie.split("=", 1)
                cookies_dict[name.strip()] = value.strip()
            else:
                print(f"Ignoring malformed cookie: '{cookie.strip()}'")
    except FileNotFoundError:
        print(f"Error: Cookies file '{file_path}' not found.")
    except IOError as e:
        print(f"Error reading cookies from file '{file_path}': {str(e)}")
    except Exception as e:
        print(f"Unexpected error reading cookies from file '{file_path}': {str(e)}")

    return cookies_dict


def fetch_document_page(args, page, session):
    url = "https://www.scribd.com/search/query"
    params = {"query": args.query, "page": page}
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        documents = data.get("results", {}).get("documents", {}).get("content", {}).get("documents", [])
        if documents:
            return documents
        raise NoDocumentsFoundError
    except requests.RequestException as e:
        print(f"Failed to fetch data for page {page}. Error: {str(e)}")
    except NoDocumentsFoundError:
        raise
    except Exception as e:
        print(f"An error occurred while fetching document page: {str(e)}")
    return []


def fetch_user(user_id, session):
    base_url = f"https://www.scribd.com/user/{user_id}/A"
    try:
        response = session.get(base_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.title
        title = title_tag.string if title_tag else "No Title Found"
        username = title.split("|")[0].strip() if title else "No Title Found"
        img_tags = soup.find_all("img", src=True)
        img_url = next((img["src"] for img in img_tags if "img/word_user/" in img["src"]), None)
        return (user_id, username, img_url)
    except requests.RequestException as e:
        print(f"Failed to fetch user {user_id}. Error: {str(e)}")
    except Exception as e:
        print(f"An error occurred while fetching user {user_id}: {str(e)}")
    return None


def search_documents(args):
    from .utils import download_and_process_document, load_filter_config

    filter_config = load_filter_config(args.filters) if args.filters else {}
    if args.detectors:
        filter_config["detectors"] = args.detectors
    max_workers = multiprocessing.cpu_count() * 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_document_page, args, page, session)
            for page in range(1, args.pages + 1)
        ]
        for future in as_completed(futures):
            try:
                documents = future.result()
                for doc in documents:
                    reader_url = doc.get("reader_url")
                    if not reader_url:
                        print("reader_url is None or missing in document:", doc)
                        continue

                    document_id = reader_url.split("/")[-2]
                    try:
                        download_and_process_document(
                            document_id,
                            session,
                            filter_config=filter_config,
                            document_format=args.document_format,
                        )
                    except Exception as e:
                        print(f"Error in download_and_process_document for {document_id}: {e}")
            except NoDocumentsFoundError:
                print("No documents found for the given query. Exiting script.")
            except Exception as e:
                print(f"An error occurred while processing documents: {e}")


def user_id_sequence(args):
    if args.user_id is not None:
        if args.user_id < 1:
            raise ValueError("--user-id must be 1 or greater.")
        return [args.user_id]

    if args.user_start < 1:
        raise ValueError("--user-start must be 1 or greater.")
    if args.user_end < args.user_start:
        raise ValueError("--user-end must be greater than or equal to --user-start.")

    return range(args.user_start, args.user_end + 1)


def search_users(args):
    if args.db:
        create_db(args.db)
        user_queue = queue.Queue()
        threading.Thread(target=insert_user, args=(user_queue, args.db)).start()
    else:
        user_queue = None

    max_workers = multiprocessing.cpu_count() * 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_user, user_id, session) for user_id in user_id_sequence(args)]
        for future in as_completed(futures):
            result = future.result()
            if not result:
                continue

            user_id, username, img_url = result
            if username and username != "No Title Found" and user_queue:
                user_queue.put((user_id, username, img_url))

    if user_queue:
        user_queue.put(None)


def signal_handler(sig, frame):
    print("\nUser keyboard interaction detected. Exiting...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="Search Scribd for documents or users.")
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")

    parser_documents = subparsers.add_parser("documents", help="Search for documents")
    parser_documents.add_argument("query", type=str, help="Search query")
    parser_documents.add_argument("-p", "--pages", type=int, default=1, help="Number of pages to search (default: 1)")
    parser_documents.add_argument("--cookies", type=str, help="Path to the cookies file")
    parser_documents.add_argument("--filters", type=str, help="Filters path to configure entity detectors")
    parser_documents.add_argument("--detectors", type=str, help="Comma-separated detectors: regex,gliner,presidio,secrets,cloud")
    parser_documents.add_argument(
        "--document-format",
        choices=["auto", "txt", "pdf", "docx"],
        default="auto",
        help="Preferred document download/read format (default: auto)",
    )
    parser_documents.set_defaults(func=search_documents)

    parser_users = subparsers.add_parser("users", help="Search for users")
    parser_users.add_argument("--user-id", type=int, help="Fetch one specific Scribd user ID")
    parser_users.add_argument("--user-start", type=int, default=1, help="Starting user ID (default: 1)")
    parser_users.add_argument("-ue", "--user-end", "--user_end", dest="user_end", type=int, default=200, help="Ending user ID (default: 200)")
    parser_users.add_argument("--db", type=str, help="SQLite database file to save data")
    parser_users.set_defaults(func=search_users)

    parser_retrieve = subparsers.add_parser("r", help="Retrieve data from SQLite database")
    parser_retrieve.add_argument("--username", type=str, help="Search by username")
    parser_retrieve.add_argument("-u", "--users", action="store_true", help="Retrieve users from the database")
    parser_retrieve.add_argument("--db", type=str, help="SQLite database file to retrieve data from")
    parser_retrieve.set_defaults(func=retrieve_data)

    args = parser.parse_args()

    global session
    session = requests.Session()

    if args.subcommand == "documents" and args.cookies:
        if not os.path.exists(args.cookies):
            print(f"Error: Cookies file '{args.cookies}' not found.")
            sys.exit(1)
        cookies = read_cookies_from_file(args.cookies)
        for name, value in cookies.items():
            session.cookies.set(name, value)
    elif args.subcommand == "documents" and not args.cookies:
        print("Error: Cookies file is required for the 'documents' subcommand.")
        parser.print_help()
        sys.exit(1)

    if args.subcommand == "documents" and args.filters:
        if not os.path.exists(args.filters):
            print(f"Error: Filters file '{args.filters}' not found.")
            sys.exit(1)

    if args.subcommand == "r" and args.username:
        search_by_username(args.username, db_file=args.db)
    elif args.subcommand:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
