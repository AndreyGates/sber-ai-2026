"""Unit tests for BIOES decode (design.md Decision 8, level 1)."""
from pii.bioes import Entity, bioes_decode, merge_entity_lists


class TestBioesDecode:
    def test_single_s_tag(self):
        tags = ["S-PERSON_NAME", "O", "O"]
        offsets = [(0, 5), (6, 10), (11, 15)]
        scores = [0.9, 0.1, 0.1]
        result = bioes_decode(tags, offsets, scores)
        assert len(result) == 1
        assert result[0] == Entity(label="PERSON_NAME", start=0, end=5, score=0.9)

    def test_bie_sequence(self):
        tags = ["B-PERSON_NAME", "I-PERSON_NAME", "E-PERSON_NAME", "O"]
        offsets = [(0, 6), (7, 13), (14, 20), (21, 25)]
        scores = [0.8, 0.85, 0.9, 0.1]
        result = bioes_decode(tags, offsets, scores)
        assert len(result) == 1
        assert result[0].label == "PERSON_NAME"
        assert result[0].start == 0
        assert result[0].end == 20
        assert abs(result[0].score - 0.85) < 0.01

    def test_multiple_entities(self):
        tags = ["S-PERSON_NAME", "O", "B-EMAIL", "E-EMAIL", "O"]
        offsets = [(0, 4), (5, 6), (7, 15), (15, 25), (26, 30)]
        scores = [0.95, 0.1, 0.8, 0.85, 0.1]
        result = bioes_decode(tags, offsets, scores)
        assert len(result) == 2
        assert result[0].label == "PERSON_NAME"
        assert result[1].label == "EMAIL"

    def test_all_o_tags(self):
        tags = ["O", "O", "O"]
        offsets = [(0, 5), (6, 10), (11, 15)]
        scores = [0.1, 0.1, 0.1]
        result = bioes_decode(tags, offsets, scores)
        assert result == []

    def test_empty_input(self):
        assert bioes_decode([], [], []) == []

    def test_b_without_e_treated_as_incomplete(self):
        tags = ["B-PERSON_NAME", "O"]
        offsets = [(0, 5), (6, 10)]
        scores = [0.9, 0.1]
        result = bioes_decode(tags, offsets, scores)
        assert len(result) == 0

    def test_mixed_labels_in_sequence(self):
        tags = ["B-PERSON_NAME", "E-PERSON_NAME", "B-EMAIL", "E-EMAIL"]
        offsets = [(0, 5), (6, 10), (11, 20), (20, 30)]
        scores = [0.9, 0.85, 0.8, 0.75]
        result = bioes_decode(tags, offsets, scores)
        assert len(result) == 2
        assert result[0].label == "PERSON_NAME"
        assert result[1].label == "EMAIL"


class TestMergeEntityLists:
    def test_no_overlap(self):
        list1 = [Entity("PERSON_NAME", 0, 5, 0.9)]
        list2 = [Entity("EMAIL", 10, 20, 0.8)]
        result = merge_entity_lists(list1, list2)
        assert len(result) == 2

    def test_exact_duplicate_keeps_max_score(self):
        list1 = [Entity("PERSON_NAME", 0, 5, 0.7)]
        list2 = [Entity("PERSON_NAME", 0, 5, 0.9)]
        result = merge_entity_lists(list1, list2)
        assert len(result) == 1
        assert result[0].score == 0.9

    def test_different_labels_same_span(self):
        list1 = [Entity("PERSON_NAME", 0, 5, 0.9)]
        list2 = [Entity("EMAIL", 0, 5, 0.8)]
        result = merge_entity_lists(list1, list2)
        assert len(result) == 2

    def test_sorted_by_start(self):
        list1 = [Entity("B", 20, 30, 0.9)]
        list2 = [Entity("A", 0, 10, 0.8)]
        result = merge_entity_lists(list1, list2)
        assert result[0].start == 0
        assert result[1].start == 20
