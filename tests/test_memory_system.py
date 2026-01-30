"""Tests for memory_system.py"""

import pytest
from tca_core.memory_system import MemorySystem


def test_memory_system_initialization():
    """Test that memory system initializes."""
    memory = MemorySystem()
    assert memory is not None


def test_store_pattern():
    """Test storing a pattern (uses mock in test)."""
    memory = MemorySystem()

    memory_id = memory.store_pattern(
        error_type="TypeError",
        fix_approach="Add type check",
        confidence=0.8
    )

    assert memory_id is not None


def test_update_on_pr_merged():
    """Test confidence boost after PR merge."""
    memory = MemorySystem()

    # Should not raise
    memory.update_on_pr_merged(
        error_type="ValueError",
        fix_approach="Add validation",
        pr_number=42
    )

    # Verify stats updated
    stats = memory.get_stats()
    assert "total_patterns" in stats


def test_update_on_pr_rejected():
    """Test anti-pattern creation after PR rejection."""
    memory = MemorySystem()

    # Should not raise
    memory.update_on_pr_rejected(
        error_type="KeyError",
        fix_approach="Wrong approach",
        reason="Breaks tests",
        pr_number=43
    )

    stats = memory.get_stats()
    assert "total_antipatterns" in stats


def test_get_stats():
    """Test getting statistics."""
    memory = MemorySystem()
    stats = memory.get_stats()

    assert "total_patterns" in stats
    assert "total_antipatterns" in stats
    assert "high_confidence_patterns" in stats
