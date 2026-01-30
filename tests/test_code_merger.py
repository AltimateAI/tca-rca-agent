"""Tests for code_merger.py"""

import pytest
from tca_core.code_merger import CodeMerger


def test_merge_python_fix():
    """Test Python function replacement with AST."""
    original = '''
def greet(name):
    print(f"Hello {name}")
    return name

def other():
    pass
'''

    fix_code = '''
def greet(name: str) -> str:
    if not name:
        raise ValueError("Name required")
    print(f"Hello {name}")
    return name
'''

    result = CodeMerger.merge_python_fix(
        original_content=original,
        fix_code=fix_code,
        function_name="greet"
    )

    # Verify fix was applied
    assert "def greet(name: str) -> str:" in result
    assert "raise ValueError" in result

    # Verify other function preserved
    assert "def other():" in result


def test_merge_preserves_other_code():
    """Test that merging preserves unrelated code."""
    original = '''
import os

def target():
    return 1

def other():
    return 2

# Comment
CONST = 42
'''

    fix_code = '''
def target():
    return 42
'''

    result = CodeMerger.merge_python_fix(
        original_content=original,
        fix_code=fix_code,
        function_name="target"
    )

    assert "import os" in result
    assert "def other():" in result
    assert "CONST = 42" in result
    assert "return 42" in result


def test_merge_generic():
    """Test generic merge method."""
    original = "def foo(): pass"
    fix_code = "def foo(): return 42"

    result = CodeMerger.merge_generic(
        original_content=original,
        fix_code=fix_code,
        file_path="test.py",
        function_name="foo"
    )

    assert "return 42" in result
