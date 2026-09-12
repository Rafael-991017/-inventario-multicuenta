import json
import os
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore

def _initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        credential = credentials.Certificate(json.loads(service_account_json))
    else:
        credential = credentials.ApplicationDefault()

    firebase_admin.initialize_app(credential, {
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    })


_initialize_firebase()
db = firestore.Client(
    project=os.getenv("FIREBASE_PROJECT_ID"),
    credentials=firebase_admin.get_app().credential.get_credential(),
    database=os.getenv("FIRESTORE_DATABASE_ID", "default"),
)


def get_db():
    """Compatibilidad con la inyección existente; devuelve el cliente Firestore."""
    yield db


def collection(name: str):
    return db.collection(name)


def document_data(snapshot) -> Optional[Dict[str, Any]]:
    if snapshot is None or not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data["id"] = int(snapshot.id)
    return data


def find_by_field(name: str, field: str, value: Any) -> Optional[Dict[str, Any]]:
    matches = collection(name).where(filter=firestore.FieldFilter(field, "==", value)).limit(1).stream()
    return document_data(next(matches, None)) if matches else None


def list_collection(name: str) -> Iterable[Dict[str, Any]]:
    for snapshot in collection(name).stream():
        data = snapshot.to_dict()
        data["id"] = int(snapshot.id)
        yield data


def next_id(name: str) -> int:
    counter = db.collection("metadata").document("counters")
    transaction = db.transaction()

    @firestore.transactional
    def increment(transaction):
        snapshot = counter.get(transaction=transaction)
        current = snapshot.to_dict().get(name, 0) if snapshot.exists else 0
        value = current + 1
        transaction.set(counter, {name: value}, merge=True)
        return value

    return increment(transaction)
