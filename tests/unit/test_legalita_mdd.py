"""Adversarial Missing-Document-Detection tasks."""

import json
from pathlib import Path

import pytest

from benchmarks.legalita.build.mdd import (
    MDD_CRITERION_TEXT,
    build_mdd_tasks,
    load_mdd_seeds,
)

_SEEDS_PATH = Path("benchmarks/legalita/data/mdd_seeds.json")


def test_seed_file_holds_exactly_twenty_scenarios():
    assert len(load_mdd_seeds(_SEEDS_PATH)) == 20


def test_every_seed_names_at_least_one_missing_document():
    for seed in load_mdd_seeds(_SEEDS_PATH):
        assert seed["missing_documents"]
        assert seed["query"].strip()


def test_seed_ids_are_unique():
    ids = [s["id"] for s in load_mdd_seeds(_SEEDS_PATH)]
    assert len(set(ids)) == len(ids)


def test_built_tasks_are_valid_mdd_tasks():
    tasks = build_mdd_tasks(load_mdd_seeds(_SEEDS_PATH))
    assert len(tasks) == 20
    for task in tasks:
        assert task.track == "mdd"
        assert task.issue_status is None
        assert task.seed_citation is None
        assert task.curated is True
        assert [c.id for c in task.criteria] == ["C-001"]
        assert task.criteria[0].required is True


def test_the_criterion_states_all_three_requirements():
    lowered = MDD_CRITERION_TEXT.lower()
    assert "assen" in lowered          # detection
    assert "astien" in lowered or "astens" in lowered  # abstention
    assert "chiede" in lowered or "richiede" in lowered  # request


def test_queries_never_reveal_that_documents_are_missing():
    for seed in load_mdd_seeds(_SEEDS_PATH):
        assert "non allegat" not in seed["query"].lower()
        assert "mancante" not in seed["query"].lower()


def test_build_rejects_a_seed_without_missing_documents():
    with pytest.raises(ValueError, match="missing_documents"):
        build_mdd_tasks([{"id": "MDD-001", "query": "q", "missing_documents": []}])
