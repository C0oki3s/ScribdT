import json
import requests
import spacy
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from tempfile import NamedTemporaryFile
import os
from presidio_analyzer import AnalyzerEngine

nlp = spacy.load("en_core_web_lg")


analyzer = AnalyzerEngine()

session = requests.Session()


def process_entity(result, text, username, documentID):
    entity_text = text[result.start:result.end]
    print(f"author: {username}")
    print(f"DocumentID: {documentID}")
    print(f"Detected entity: {result.entity_type}")
    print(f"Data: {entity_text}")
    print("-" * 30)

def download_and_process_document(document_id, session, entities_to_detect):
    initial_url = f"https://www.scribd.com/doc-page/download-receipt-modal-props/{document_id}"
    response = session.get(initial_url)
    
    if response.status_code == 200:
        data = response.json()
        download_url = data['document']['download_url']
        username = data['document']['author']['name']
        secret_password = data['document']['access_key']
        download_url_with_secret = f"{download_url}?secret_password={secret_password}&extension=txt"
        headers = {
            'User-Agent': 'ScribdT Tool',
        }
        
        response = session.get(download_url_with_secret, headers=headers)

        if response.status_code == 200:
            try:
                downloaded_text = response.content.decode('utf-8')
            except UnicodeDecodeError:
                downloaded_text = response.content.decode('ascii', 'replace')
            doc = nlp(downloaded_text)
            
            results = analyzer.analyze(text=downloaded_text, entities=entities_to_detect, language="en")
            max_workers = multiprocessing.cpu_count() * 5
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for result in results:
                    future = executor.submit(process_entity, result, downloaded_text, username, document_id)
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        future.result()  
                    except Exception as e:
                        print(f"An error occurred during entity processing: {e}")
            
        else:
            print(f"Failed to download text file. Status code: {response.status_code}")
    else:
        print(f"Failed to retrieve document information. Status code: {response.status_code}")