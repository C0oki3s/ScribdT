import io
import json

from bs4 import BeautifulSoup

from .detectors import DEFAULT_DETECTORS, DEFAULT_GLINER_LABELS, detect_entities

ENTITY_ALIASES = {
    "ADDRESS": "LOCATION",
    "CITY": "LOCATION",
    "COUNTRY": "LOCATION",
    "DOB": "DATE_TIME",
    "DRIVER_LICENSE": "US_DRIVER_LICENSE",
    "FULL_NAME": "FULL_NAME",
    "IBAN": "IBAN_CODE",
    "IN_PHONE_NUMBER": "PHONE_NUMBER",
    "PASSPORT_NUMBER": "US_PASSPORT",
    "POSTCODE": "LOCATION",
    "SSN": "US_SSN",
    "STATE": "LOCATION",
    "STREET_ADDRESS": "LOCATION",
    "UK_PHONE_NUMBER": "PHONE_NUMBER",
    "US_PHONE_NUMBER": "PHONE_NUMBER",
    "ZIPCODE": "LOCATION",
}

PRESIDIO_SUPPORTED_ENTITIES = {
    "CREDIT_CARD",
    "CRYPTO",
    "DATE_TIME",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "MEDICAL_LICENSE",
    "NRP",
    "PERSON",
    "PHONE_NUMBER",
    "URL",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "US_SSN",
}

DEFAULT_FILTER_CONFIG = {
    "entities": None,
    "presidio_entities": None,
    "detectors": DEFAULT_DETECTORS.copy(),
    "score_threshold": 0.45,
    "context": None,
    "allow_list": None,
    "exclude_terms": [],
    "exclude_regex": [],
    "gliner_model": "urchade/gliner_medium-v2.1",
    "gliner_labels": DEFAULT_GLINER_LABELS.copy(),
    "gliner_threshold": 0.45,
}


def load_filter_config(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_config = json.load(f)
    return normalize_filter_config(raw_config)


def normalize_filter_config(raw_config):
    config = copy_default_filter_config()
    if not raw_config:
        return config

    if isinstance(raw_config, list):
        raw_entities = raw_config
    elif isinstance(raw_config, dict):
        raw_entities = raw_config.get("entities")
        config["detectors"] = normalize_detectors(raw_config.get("detectors"), config["detectors"])
        config["score_threshold"] = raw_config.get("score_threshold", config["score_threshold"])
        config["context"] = _clean_string_list(raw_config.get("context"))
        config["allow_list"] = _clean_string_list(raw_config.get("allow_list"))
        config["exclude_terms"] = _clean_string_list(raw_config.get("exclude_terms")) or []
        config["exclude_regex"] = _clean_string_list(raw_config.get("exclude_regex")) or []
        config["gliner_model"] = raw_config.get("gliner_model", config["gliner_model"])
        config["gliner_labels"] = _clean_string_list(raw_config.get("gliner_labels")) or config["gliner_labels"]
        config["gliner_threshold"] = raw_config.get("gliner_threshold", config["gliner_threshold"])
    else:
        raise ValueError("Filters must be a JSON object or a list of entity names.")

    config["entities"] = normalize_entities(raw_entities)
    config["presidio_entities"] = normalize_presidio_entities(config["entities"])

    if config["score_threshold"] is not None:
        config["score_threshold"] = float(config["score_threshold"])
        if not 0 <= config["score_threshold"] <= 1:
            raise ValueError("score_threshold must be between 0 and 1.")

    config["gliner_threshold"] = float(config["gliner_threshold"])
    if not 0 <= config["gliner_threshold"] <= 1:
        raise ValueError("gliner_threshold must be between 0 and 1.")

    return config


def copy_default_filter_config():
    config = DEFAULT_FILTER_CONFIG.copy()
    config["detectors"] = DEFAULT_FILTER_CONFIG["detectors"].copy()
    config["gliner_labels"] = DEFAULT_FILTER_CONFIG["gliner_labels"].copy()
    config["exclude_terms"] = DEFAULT_FILTER_CONFIG["exclude_terms"].copy()
    config["exclude_regex"] = DEFAULT_FILTER_CONFIG["exclude_regex"].copy()
    return config


def normalize_detectors(raw_detectors, default_detectors):
    if raw_detectors is None:
        return default_detectors
    if isinstance(raw_detectors, str):
        raw_detectors = raw_detectors.split(",")
    detectors = [str(detector).strip().lower() for detector in raw_detectors if str(detector).strip()]
    return detectors or default_detectors


def normalize_entities(raw_entities):
    if not raw_entities:
        return None

    entities = []
    for entity in raw_entities:
        entity_name = str(entity).strip().upper()
        if not entity_name:
            continue
        entities.append(ENTITY_ALIASES.get(entity_name, entity_name))
    return sorted(set(entities)) or None


def normalize_presidio_entities(entities):
    if not entities:
        return None
    return sorted(entity for entity in entities if entity in PRESIDIO_SUPPORTED_ENTITIES) or None


def _clean_string_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def process_entity(result, text, username, documentID):
    entity_text = text[result.start:result.end]
    merged_sources = result.metadata.get("merged_sources", [result.source])
    print(f"author: {username}")
    print(f"DocumentID: {documentID}")
    print(f"Detected entity: {result.entity_type}")
    print(f"Source: {', '.join(merged_sources)}")
    print(f"Score: {result.score:.2f}")
    print(f"Data: {entity_text}")
    print("-" * 30)


def download_and_process_document(document_id, session, filter_config=None, document_format="auto"):
    filter_config = normalize_filter_config(filter_config)
    initial_url = f"https://www.scribd.com/doc-page/download-receipt-modal-props/{document_id}"
    response = session.get(initial_url, timeout=30)
    if response.status_code == 200:
        data = response.json()
        document = data.get("document", {})
        download_url = document.get("download_url")
        username = document.get("author", {}).get("name", "Unknown Author")
        secret_password = document.get("access_key")

        if not download_url or not secret_password:
            print(f"Document {document_id}: missing download metadata.")
            return

        downloaded_text = None
        for extension in _candidate_extensions(document_format):
            download_url_with_secret = f"{download_url}?secret_password={secret_password}&extension={extension}"
            headers = {"User-Agent": "ScribdT Tool"}
            print(f"Downloading document {document_id} as {extension}")
            document_response = session.get(download_url_with_secret, headers=headers, timeout=60)

            if document_response.status_code != 200:
                print(f"Failed to download {extension}. Status code: {document_response.status_code}")
                continue

            downloaded_text = extract_text(document_response, extension)
            if _has_useful_text(downloaded_text):
                break
            print(f"Downloaded {extension}, but no useful text was extracted.")

        if not _has_useful_text(downloaded_text):
            print(f"Document {document_id}: no readable text extracted.")
            return

        results = analyze_document_text(downloaded_text, filter_config)
        for result in results:
            process_entity(result, downloaded_text, username, document_id)
    else:
        print(f"Failed to retrieve document information. Status code: {response.status_code}")


def _candidate_extensions(document_format):
    if document_format and document_format != "auto":
        return [document_format]
    return ["txt", "pdf", "docx"]


def _has_useful_text(text):
    return bool(text and len(text.strip()) >= 20)


def extract_text(response, requested_extension="txt"):
    content_type = response.headers.get("content-type", "").lower()
    content = response.content

    if content.startswith(b"%PDF") or requested_extension == "pdf" or "pdf" in content_type:
        return extract_pdf_text(content)
    if content.startswith(b"PK") or requested_extension == "docx":
        return extract_docx_text(content)
    if "html" in content_type:
        return extract_html_text(content, response.encoding)
    return decode_text(content, response.encoding)


def decode_text(content, encoding=None):
    for candidate in [encoding, "utf-8", "utf-16", "latin-1"]:
        if not candidate:
            continue
        try:
            return content.decode(candidate)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def extract_html_text(content, encoding=None):
    html = decode_text(content, encoding)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def extract_pdf_text(content):
    try:
        from pypdf import PdfReader
    except ImportError:
        print("PDF extraction requires pypdf. Install it with: pip install pypdf")
        return ""

    reader = PdfReader(io.BytesIO(content))
    page_text = []
    for page in reader.pages:
        page_text.append(page.extract_text() or "")
    return "\n".join(page_text)


def extract_docx_text(content):
    try:
        from docx import Document
    except ImportError:
        print("DOCX extraction requires python-docx. Install it with: pip install python-docx")
        return ""

    document = Document(io.BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def analyze_document_text(text, filter_config):
    return detect_entities(text, filter_config)
