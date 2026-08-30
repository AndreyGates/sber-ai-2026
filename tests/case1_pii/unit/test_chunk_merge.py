"""Unit tests for chunk merge (design.md Decision 8, level 1)."""
from pii.bioes import Entity
from pii.chunk_merge import merge_chunk_entities


class TestChunkMerge:
    def test_no_overlap(self):
        chunks = [
            [Entity("PERSON_NAME", 0, 5, 0.9)],
            [Entity("EMAIL", 20, 30, 0.8)],
        ]
        spans = [(0, 15), (10, 35)]
        result = merge_chunk_entities(chunks, spans)
        assert len(result) == 2

    def test_exact_duplicate_keeps_max_score(self):
        chunks = [
            [Entity("PERSON_NAME", 8, 15, 0.7)],
            [Entity("PERSON_NAME", 8, 15, 0.9)],
        ]
        spans = [(0, 20), (5, 25)]
        result = merge_chunk_entities(chunks, spans)
        assert len(result) == 1
        assert result[0].score == 0.9

    def test_partial_overlap_keeps_max_score(self):
        chunks = [
            [Entity("PERSON_NAME", 8, 18, 0.7)],
            [Entity("PERSON_NAME", 10, 20, 0.9)],
        ]
        spans = [(0, 20), (5, 25)]
        result = merge_chunk_entities(chunks, spans)
        assert len(result) == 1
        assert result[0].score == 0.9

    def test_contained_entity_keeps_outer(self):
        chunks = [
            [Entity("PERSON_NAME", 5, 25, 0.9)],
            [Entity("PERSON_NAME", 10, 20, 0.8)],
        ]
        spans = [(0, 30), (5, 30)]
        result = merge_chunk_entities(chunks, spans)
        assert len(result) == 1
        assert result[0].start == 5
        assert result[0].end == 25

    def test_empty_chunks(self):
        result = merge_chunk_entities([], [])
        assert result == []

    def test_empty_entity_lists(self):
        chunks = [[], []]
        spans = [(0, 10), (5, 15)]
        result = merge_chunk_entities(chunks, spans)
        assert result == []

    def test_different_labels_not_merged(self):
        chunks = [
            [Entity("PERSON_NAME", 5, 15, 0.9)],
            [Entity("EMAIL", 5, 15, 0.8)],
        ]
        spans = [(0, 20), (5, 25)]
        result = merge_chunk_entities(chunks, spans)
        assert len(result) == 2

    def test_sorted_output(self):
        chunks = [
            [Entity("B", 20, 30, 0.9)],
            [Entity("A", 0, 10, 0.8)],
        ]
        spans = [(0, 15), (10, 35)]
        result = merge_chunk_entities(chunks, spans)
        assert result[0].start < result[1].start
