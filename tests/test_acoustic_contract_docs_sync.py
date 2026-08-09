from dataclasses import fields
from pathlib import Path

from subsim.acoustic_contract import (
    EVENT_CUE_TYPES,
    SCHEMA_VERSION,
    AcousticContactState,
    AcousticFoundationState,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_DOC = REPO_ROOT / "docs" / "ACOUSTIC_CONTRACT.md"


def test_contract_doc_mentions_schema_and_struct_fields() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    assert SCHEMA_VERSION in text

    for field in fields(AcousticFoundationState):
        assert field.name in text
    for field in fields(AcousticContactState):
        assert field.name in text


def test_contract_doc_mentions_event_taxonomy_and_surface_signals() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    for cue in EVENT_CUE_TYPES:
        assert cue in text

    required_surface_tokens = (
        "mix_contact",
        "sfx_ping",
        "sfx_fire",
        "sfx_return",
        "acoustic.schema_version",
        "acoustic.foundation",
        "acoustic.contacts",
    )
    for token in required_surface_tokens:
        assert token in text
