"""DedupEngine — fingerprint-based deduplication bridge between parsers and storage."""

from __future__ import annotations

from src.core.models.parsed_candidate import ParsedCandidate
from src.core.models.promotion import Promotion
from src.core.ports.storage import IStorageBackend


class DedupEngine:
    """Content-fingerprint-based deduplication engine.

    Determines whether a ParsedCandidate represents a genuinely new promotion
    by computing its content fingerprint and checking against the persistent
    storage backend. Only depends on IStorageBackend (no concrete adapter imports).

    Per Blueprint Section 2.1 and 3.2 Phase 4, dedup uses SHA256 of the
    content_snippet to detect structurally identical promotions even when URLs
    or IDs change slightly.
    """

    def __init__(self, storage: IStorageBackend) -> None:
        """Initialise the dedup engine with a storage backend.

        Args:
            storage: An IStorageBackend implementation providing
                get_promotion_by_fingerprint() for fingerprint lookups.
        """
        self._storage = storage

    async def is_new_promotion(self, parsed_candidate: ParsedCandidate) -> bool:
        """Determine whether a parsed candidate represents a new, unseen promotion.

        Computes the SHA256 content fingerprint from the candidate's content_snippet,
        then queries the storage backend for an existing promotion with the same
        fingerprint. Returns True only if no existing match is found.

        Args:
            parsed_candidate: The parsed candidate to check (frozen dataclass,
                read-only access only — never mutated).

        Returns:
            True if this fingerprint has never been seen before (new promotion),
            False if a matching promotion already exists in storage.

        Raises:
            StorageError: Propagated from the storage backend on database failures.
        """
        fingerprint = Promotion.compute_fingerprint(parsed_candidate.content_snippet)
        existing = await self._storage.get_promotion_by_fingerprint(fingerprint)
        return existing is None