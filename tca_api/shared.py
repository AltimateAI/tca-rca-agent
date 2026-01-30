"""
Shared instances across API routes
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tca_core.memory_system import MemorySystem

# Shared memory system instance (singleton)
# All routes should import this instead of creating their own
memory_system = MemorySystem()

print("✅ Shared memory system initialized")
