from dataclasses import dataclass, field
import re


@dataclass
class DetectionResult:
    start: int
    end: int
    entity_type: str
    score: float
    source: str
    metadata: dict = field(default_factory=dict)


DEFAULT_DETECTORS = ["regex", "gliner", "presidio", "secrets"]
DEFAULT_GLINER_LABELS = [
    "person",
    "first name",
    "last name",
    "full name",
    "username",
    "email address",
    "phone number",
    "address",
    "location",
    "organization",
    "passport number",
    "driver license",
    "national id",
    "password",
    "api key",
    "token",
]

REGEX_PATTERNS = [
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), 0.92),
    ("IP_ADDRESS", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), 0.85),
    ("URL", re.compile(r"\bhttps?://[^\s<>'\"]+", re.IGNORECASE), 0.85),
    ("PHONE_NUMBER", re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)"), 0.55),
    ("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)"), 0.65),
]

SECRET_PATTERNS = [
    ("PASSWORD_CANDIDATE", re.compile(r"(?i)\b(?:password|passwd|pwd|pass)\s*[:=]\s*['\"]?([^'\"\s,;]{4,})"), 0.78, 1),
    ("API_KEY", re.compile(r"(?i)\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})"), 0.82, 1),
    ("TOKEN", re.compile(r"(?i)\b(?:token|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9._\-]{20,})"), 0.82, 1),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0.95, 0),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), 0.98, 0),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), 0.9, 0),
]

GLINER_TYPE_MAP = {
    "person": "PERSON",
    "first name": "FIRST_NAME",
    "last name": "LAST_NAME",
    "full name": "FULL_NAME",
    "username": "USERNAME",
    "email address": "EMAIL_ADDRESS",
    "phone number": "PHONE_NUMBER",
    "address": "LOCATION",
    "location": "LOCATION",
    "organization": "ORGANIZATION",
    "passport number": "PASSPORT_NUMBER",
    "driver license": "DRIVER_LICENSE",
    "national id": "NATIONAL_ID",
    "password": "PASSWORD_CANDIDATE",
    "api key": "API_KEY",
    "token": "TOKEN",
}

_gliner_model = None


def normalize_detector_names(detectors):
    if not detectors:
        return DEFAULT_DETECTORS.copy()
    if isinstance(detectors, str):
        detectors = [part.strip() for part in detectors.split(",")]
    names = []
    for detector in detectors:
        name = str(detector).strip().lower()
        if name:
            names.append(name)
    return names or DEFAULT_DETECTORS.copy()


def detect_entities(text, filter_config):
    detector_names = normalize_detector_names(filter_config.get("detectors"))
    results = []

    if "regex" in detector_names:
        results.extend(run_regex_validators(text))
    if "gliner" in detector_names:
        results.extend(run_gliner(text, filter_config))
    if "presidio" in detector_names:
        results.extend(run_presidio(text, filter_config))
    if "secrets" in detector_names:
        results.extend(run_secret_scanner(text))
    if "cloud" in detector_names:
        print("Cloud PII backend is configured as a future extension and is not implemented yet.")

    results = filter_by_entities(results, filter_config.get("entities"))
    results = reject_excluded_results(results, text, filter_config)
    return merge_results(results)


def run_regex_validators(text):
    results = []
    for entity_type, pattern, score in REGEX_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if entity_type == "CREDIT_CARD" and not passes_luhn(text[start:end]):
                continue
            results.append(DetectionResult(start, end, entity_type, score, "regex"))
    return results


def run_secret_scanner(text):
    results = []
    for entity_type, pattern, score, group_index in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span(group_index) if group_index else match.span()
            results.append(DetectionResult(start, end, entity_type, score, "secrets"))
    return results


def run_presidio(text, filter_config):
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        print("Presidio detector requested but presidio-analyzer is not installed.")
        return []

    analyzer = AnalyzerEngine()
    try:
        presidio_results = analyzer.analyze(
            text=text,
            entities=filter_config.get("presidio_entities"),
            language="en",
            score_threshold=filter_config.get("score_threshold"),
            context=filter_config.get("context"),
            allow_list=filter_config.get("allow_list"),
        )
    except Exception as e:
        print(f"Presidio analysis failed: {e}")
        return []

    return [
        DetectionResult(result.start, result.end, result.entity_type, result.score, "presidio")
        for result in presidio_results
    ]


def run_gliner(text, filter_config):
    labels = filter_config.get("gliner_labels") or DEFAULT_GLINER_LABELS
    model_name = filter_config.get("gliner_model", "urchade/gliner_medium-v2.1")
    threshold = filter_config.get("gliner_threshold", 0.45)

    try:
        model = get_gliner_model(model_name)
    except ImportError:
        print("GLiNER detector requested but gliner is not installed.")
        return []
    except Exception as e:
        print(f"GLiNER model could not be loaded: {e}")
        return []

    results = []
    for offset, chunk in text_chunks(text):
        try:
            entities = model.predict_entities(chunk, labels, threshold=threshold)
        except Exception as e:
            print(f"GLiNER analysis failed: {e}")
            return results

        for entity in entities:
            label = str(entity.get("label", "")).lower()
            entity_type = GLINER_TYPE_MAP.get(label, label.upper().replace(" ", "_"))
            results.append(
                DetectionResult(
                    offset + int(entity["start"]),
                    offset + int(entity["end"]),
                    entity_type,
                    float(entity.get("score", threshold)),
                    "gliner",
                    {"label": entity.get("label")},
                )
            )
    return results


def get_gliner_model(model_name):
    global _gliner_model
    if _gliner_model is not None:
        return _gliner_model
    from gliner import GLiNER

    _gliner_model = GLiNER.from_pretrained(model_name)
    return _gliner_model


def text_chunks(text, chunk_size=2500, overlap=250):
    if len(text) <= chunk_size:
        yield 0, text
        return

    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            next_space = text.rfind(" ", start, end)
            if next_space > start + chunk_size // 2:
                end = next_space
        yield start, text[start:end]
        if end == len(text):
            break
        start = max(end - overlap, start + 1)


def filter_by_entities(results, entities):
    if not entities:
        return results
    allowed = {str(entity).upper() for entity in entities}
    return [result for result in results if result.entity_type.upper() in allowed]


def reject_excluded_results(results, text, filter_config):
    exclude_terms = {term.lower() for term in filter_config.get("exclude_terms", [])}
    exclude_patterns = [
        re.compile(pattern, re.IGNORECASE)
        for pattern in filter_config.get("exclude_regex", [])
    ]

    filtered_results = []
    for result in results:
        entity_text = text[result.start:result.end].strip()
        if entity_text.lower() in exclude_terms:
            continue
        if any(pattern.search(entity_text) for pattern in exclude_patterns):
            continue
        filtered_results.append(result)
    return filtered_results


def merge_results(results):
    sorted_results = sorted(results, key=lambda item: (item.start, -(item.end - item.start), -item.score))
    merged = []

    for result in sorted_results:
        overlaps = [
            existing for existing in merged
            if result.start < existing.end and existing.start < result.end
        ]
        if not overlaps:
            merged.append(result)
            continue

        strongest = max(overlaps, key=lambda item: (item.score, item.end - item.start))
        if result.score > strongest.score:
            merged.remove(strongest)
            result.metadata["merged_sources"] = sorted({result.source, strongest.source})
            merged.append(result)
        elif result.entity_type == strongest.entity_type:
            strongest.score = max(strongest.score, result.score)
            sources = set(strongest.metadata.get("merged_sources", [strongest.source]))
            sources.add(result.source)
            strongest.metadata["merged_sources"] = sorted(sources)

    return sorted(merged, key=lambda item: item.start)


def passes_luhn(value):
    digits = [int(char) for char in re.sub(r"\D", "", value)]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0
