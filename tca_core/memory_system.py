"""
Memory System with Mem0 Integration
Stores learned patterns and anti-patterns for self-improvement
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .config import MEM0_API_KEY, MEM0_ORG_ID, MEM0_PROJECT_ID


class MemorySystem:
    """
    Memory system for storing and retrieving learned patterns.

    Uses Mem0 free tier (1,000 memories/month) in production.
    Falls back to in-memory storage for testing/dry-run.
    """

    def __init__(self, agent_id: str = "tca-rca-agent"):
        """
        Initialize memory system.

        Args:
            agent_id: Unique identifier for this agent instance
        """
        self.agent_id = agent_id
        self.use_mock = not MEM0_API_KEY

        # Pattern caching to reduce Mem0 API calls
        self._patterns_cache = None
        self._cache_timestamp = None
        self._cache_ttl_seconds = 300  # 5 minutes

        if not self.use_mock:
            try:
                from mem0 import MemoryClient

                self.client = MemoryClient(
                    api_key=MEM0_API_KEY,
                    org_id=MEM0_ORG_ID,
                    project_id=MEM0_PROJECT_ID
                )
                print("✅ Mem0 client initialized (with org + project)")
            except ImportError:
                print("⚠️  mem0ai package not installed, using mock memory")
                self.use_mock = True
                self._init_mock()
            except Exception as e:
                print(f"⚠️  Failed to initialize Mem0: {e}")
                print("   Using mock memory system")
                self.use_mock = True
                self._init_mock()
        else:
            print("📝 Using mock memory system")
            self._init_mock()

    def _init_mock(self):
        """Initialize mock in-memory storage."""
        self.mock_memories: List[Dict] = []

    def get_all_patterns(self) -> str:
        """
        Get all learned patterns as a formatted string.

        Uses in-memory caching (5 min TTL) to reduce Mem0 API calls.

        IMPORTANT: Returns IDENTICAL text every time for prompt caching.
        Do NOT include timestamps or random IDs.

        Returns:
            Formatted string of all patterns
        """
        if self.use_mock:
            return self._get_mock_patterns()

        # Check cache first
        now = datetime.utcnow()
        if self._patterns_cache and self._cache_timestamp:
            age = (now - self._cache_timestamp).total_seconds()
            if age < self._cache_ttl_seconds:
                # Cache hit - return cached patterns
                return self._patterns_cache

        # Cache miss - fetch from Mem0
        try:
            # Get all memories from Mem0
            memories = []

            try:
                # Use get_all with proper filters (v2 API requires AND/OR wrapper)
                # Note: Using agent_id instead of user_id for agent knowledge storage
                response = self.client.get_all(
                    filters={
                        "AND": [
                            {"agent_id": self.agent_id}
                        ]
                    },
                    page_size=100
                )

                # Handle response format
                if isinstance(response, dict):
                    if 'results' in response:
                        memories = response['results']
                    elif 'memories' in response:
                        memories = response['memories']
                    else:
                        memories = []
                elif isinstance(response, list):
                    memories = response
                else:
                    memories = []

                print(f"✅ Retrieved {len(memories)} memories from Mem0")

            except Exception as e:
                print(f"⚠️  Could not retrieve memories: {e}")
                # Return empty patterns but don't fail
                return "No learned patterns yet (storage active, retrieval pending async processing)"

            if not memories:
                return "No learned patterns yet."

            # Format patterns for prompt
            patterns = []
            antipatterns = []

            for mem in memories:
                metadata = mem.get("metadata", {})
                category = metadata.get("category", "unknown")
                confidence = metadata.get("confidence", 0.5)

                if category == "error_pattern" and confidence >= 0.7:
                    error_type = metadata.get("error_type", "Unknown")
                    content = mem.get("memory", "")
                    patterns.append(
                        f"- {error_type} (confidence: {confidence:.0%}): {content}"
                    )
                elif category == "antipattern" and confidence >= 0.7:
                    error_type = metadata.get("error_type", "Unknown")
                    failed_approach = metadata.get("failed_approach", "")
                    reason = metadata.get("reason", "")
                    antipatterns.append(
                        f"- {error_type}: AVOID '{failed_approach}' ({reason})"
                    )

            # Build formatted string (MUST be identical each call for caching)
            result = []
            if patterns:
                result.append("## Learned Successful Patterns")
                result.extend(sorted(patterns))  # Sort for consistency
            if antipatterns:
                result.append("\n## Anti-Patterns (What NOT to Do)")
                result.extend(sorted(antipatterns))

            formatted_patterns = "\n".join(result) if result else "No learned patterns yet."

            # Cache the result
            self._patterns_cache = formatted_patterns
            self._cache_timestamp = now

            return formatted_patterns

        except Exception as e:
            print(f"⚠️  Error retrieving patterns: {e}")
            return "Error retrieving learned patterns."

    def get_patterns_by_error_type(self, error_type: str) -> str:
        """
        Get learned patterns filtered by error type.

        This method enables better prompt caching for batch analysis of similar issues.
        All issues of the same error type will get the same cached pattern context.

        Args:
            error_type: Error type to filter by (e.g., "KeyError", "DatabaseError")

        Returns:
            Formatted string of patterns for this error type only
        """
        all_patterns = self.get_all_patterns()

        if not all_patterns or all_patterns.startswith("No learned patterns"):
            return all_patterns

        # Filter patterns to only those matching the error type
        lines = all_patterns.split('\n')
        filtered = []
        in_section = False

        for line in lines:
            # Keep section headers
            if line.startswith('##'):
                filtered.append(line)
                in_section = True
            # Filter pattern lines by error type
            elif line.strip().startswith('-'):
                # Extract error type from pattern line (format: "- ErrorType ...")
                if error_type.lower() in line.lower():
                    filtered.append(line)
            elif in_section:
                # Keep blank lines between sections
                filtered.append(line)

        result = '\n'.join(filtered).strip()
        return result if result else f"No learned patterns yet for {error_type}."

    def _get_mock_patterns(self) -> str:
        """Get patterns from mock storage."""
        if not self.mock_memories:
            # Return some default patterns for testing
            return """## Learned Successful Patterns
- AttributeError (confidence: 90%): Add null check before accessing attributes on potentially None values
- KeyError (confidence: 85%): Use .get() method instead of direct dict access
- TypeError (confidence: 80%): Add type hints and validation for function parameters
- IndexError (confidence: 85%): Check list length before accessing by index

## Anti-Patterns (What NOT to Do)
- AttributeError: AVOID 'silently catching without logging' (makes debugging harder)
- TypeError: AVOID 'using type() == check instead of isinstance()' (breaks inheritance)"""

        # Format mock memories
        patterns = []
        antipatterns = []

        for mem in self.mock_memories:
            if mem["category"] == "error_pattern" and mem["confidence"] >= 0.7:
                patterns.append(
                    f"- {mem['error_type']} (confidence: {mem['confidence']:.0%}): {mem['fix_approach']}"
                )
            elif mem["category"] == "antipattern" and mem["confidence"] >= 0.7:
                antipatterns.append(
                    f"- {mem['error_type']}: AVOID '{mem['failed_approach']}' ({mem['reason']})"
                )

        result = []
        if patterns:
            result.append("## Learned Successful Patterns")
            result.extend(sorted(patterns))
        if antipatterns:
            result.append("\n## Anti-Patterns (What NOT to Do)")
            result.extend(sorted(antipatterns))

        return "\n".join(result) if result else "No learned patterns yet."

    def store_pattern(
        self,
        error_type: str,
        fix_approach: str,
        confidence: float = 0.5,
        additional_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Store a successful fix pattern.

        Args:
            error_type: Type of error (e.g., 'TypeError', 'AttributeError')
            fix_approach: Description of the fix approach
            confidence: Initial confidence (0.0-1.0)
            additional_metadata: Optional extra metadata

        Returns:
            Memory ID
        """
        if self.use_mock:
            return self._store_mock_pattern(
                error_type, fix_approach, confidence, additional_metadata
            )

        try:
            metadata = {
                "category": "error_pattern",
                "error_type": error_type,
                "confidence": confidence,
                "status": "pending",  # Updated to success/failed later
                "stored_at": datetime.utcnow().isoformat(),
                **(additional_metadata or {}),
            }

            result = self.client.add(
                messages=[
                    {
                        "role": "assistant",
                        "content": f"{error_type}: {fix_approach}",
                    }
                ],
                agent_id=self.agent_id,
                metadata=metadata,
            )

            memory_id = result.get("id", "")
            print(f"✅ Stored pattern: {error_type} (ID: {memory_id[:8]}...)")
            return memory_id

        except Exception as e:
            print(f"⚠️  Error storing pattern: {e}")
            return ""

    def _store_mock_pattern(
        self, error_type: str, fix_approach: str, confidence: float, metadata: Optional[Dict]
    ) -> str:
        """Store pattern in mock storage."""
        memory = {
            "id": f"mock-{len(self.mock_memories)}",
            "category": "error_pattern",
            "error_type": error_type,
            "fix_approach": fix_approach,
            "confidence": confidence,
            "status": "pending",
            "stored_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        self.mock_memories.append(memory)
        print(f"✅ [MOCK] Stored pattern: {error_type}")
        return memory["id"]

    def update_on_pr_merged(
        self, error_type: str, fix_approach: str, pr_number: int
    ):
        """
        Update confidence when PR is merged successfully.

        This boosts confidence for this pattern.

        Args:
            error_type: Type of error that was fixed
            fix_approach: The approach that worked
            pr_number: GitHub PR number
        """
        if self.use_mock:
            self._update_mock_on_pr_merged(error_type, fix_approach, pr_number)
            return

        try:
            # Store success as new high-confidence memory
            self.client.add(
                messages=[
                    {
                        "role": "assistant",
                        "content": f"Successfully fixed {error_type} using: {fix_approach}",
                    }
                ],
                agent_id=self.agent_id,
                metadata={
                    "category": "error_pattern",
                    "error_type": error_type,
                    "confidence": 0.9,  # High confidence after merge
                    "status": "success",
                    "pr_number": pr_number,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            print(f"✅ Learned! Boosted confidence for {error_type} (PR #{pr_number})")

        except Exception as e:
            print(f"⚠️  Error updating on PR merge: {e}")

    def _update_mock_on_pr_merged(
        self, error_type: str, fix_approach: str, pr_number: int
    ):
        """Update mock memory on PR merge."""
        memory = {
            "id": f"mock-success-{len(self.mock_memories)}",
            "category": "error_pattern",
            "error_type": error_type,
            "fix_approach": fix_approach,
            "confidence": 0.9,
            "status": "success",
            "pr_number": pr_number,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.mock_memories.append(memory)
        print(f"✅ [MOCK] Learned! Boosted confidence for {error_type}")

    def update_on_pr_rejected(
        self, error_type: str, fix_approach: str, reason: str, pr_number: int
    ):
        """
        Create anti-pattern when PR is rejected.

        This teaches the system what NOT to do.

        Args:
            error_type: Type of error
            fix_approach: The approach that DIDN'T work
            reason: Why it was rejected
            pr_number: GitHub PR number
        """
        if self.use_mock:
            self._update_mock_on_pr_rejected(
                error_type, fix_approach, reason, pr_number
            )
            return

        try:
            # Store anti-pattern
            self.client.add(
                messages=[
                    {
                        "role": "assistant",
                        "content": f"Failed fix for {error_type}: {fix_approach}. Reason: {reason}",
                    }
                ],
                agent_id=self.agent_id,
                metadata={
                    "category": "antipattern",
                    "error_type": error_type,
                    "failed_approach": fix_approach,
                    "reason": reason,
                    "confidence": 0.9,  # High confidence this DOESN'T work
                    "pr_number": pr_number,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

            print(f"❌ Learned! Created anti-pattern for {error_type} (PR #{pr_number})")

        except Exception as e:
            print(f"⚠️  Error updating on PR rejection: {e}")

    def _update_mock_on_pr_rejected(
        self, error_type: str, fix_approach: str, reason: str, pr_number: int
    ):
        """Update mock memory on PR rejection."""
        memory = {
            "id": f"mock-antipattern-{len(self.mock_memories)}",
            "category": "antipattern",
            "error_type": error_type,
            "failed_approach": fix_approach,
            "reason": reason,
            "confidence": 0.9,
            "pr_number": pr_number,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.mock_memories.append(memory)
        print(f"❌ [MOCK] Learned! Created anti-pattern for {error_type}")

    def get_stats(self) -> Dict:
        """Get learning statistics."""
        if self.use_mock:
            return self._get_mock_stats()

        try:
            # Get all memories using get_all with filters
            try:
                response = self.client.get_all(
                    filters={
                        "AND": [
                            {"agent_id": self.agent_id}
                        ]
                    },
                    page_size=100
                )
                # Handle response format
                if isinstance(response, dict):
                    if 'results' in response:
                        all_memories = response['results']
                    elif 'memories' in response:
                        all_memories = response['memories']
                    else:
                        all_memories = []
                elif isinstance(response, list):
                    all_memories = response
                else:
                    all_memories = []
            except Exception as e:
                print(f"⚠️  Could not retrieve stats: {e}")
                all_memories = []

            patterns = [
                m
                for m in all_memories
                if m.get("metadata", {}).get("category") == "error_pattern"
            ]
            antipatterns = [
                m
                for m in all_memories
                if m.get("metadata", {}).get("category") == "antipattern"
            ]

            return {
                "total_patterns": len(patterns),
                "total_antipatterns": len(antipatterns),
                "high_confidence_patterns": len(
                    [
                        p
                        for p in patterns
                        if p.get("metadata", {}).get("confidence", 0) >= 0.8
                    ]
                ),
                "total_memories": len(all_memories),
                "mode": "MEM0",
            }
        except Exception as e:
            return {
                "total_patterns": 0,
                "total_antipatterns": 0,
                "high_confidence_patterns": 0,
                "total_memories": 0,
                "mode": "MOCK" if self.use_mock else None,
                "error": str(e)
            }

    def _get_mock_stats(self) -> Dict:
        """Get stats from mock storage."""
        patterns = [m for m in self.mock_memories if m["category"] == "error_pattern"]
        antipatterns = [m for m in self.mock_memories if m["category"] == "antipattern"]

        return {
            "total_patterns": len(patterns),
            "total_antipatterns": len(antipatterns),
            "high_confidence_patterns": len([p for p in patterns if p["confidence"] >= 0.8]),
            "total_memories": len(self.mock_memories),
            "mode": "MOCK",
        }

    def _get_bootstrap_tracker_path(self) -> Path:
        """Get path to bootstrap tracker file."""
        return Path.home() / ".tca" / "bootstrap_tracker.json"

    def check_bootstrap_needed(self) -> bool:
        """
        Check if bootstrap is needed.

        Returns True if:
        - Never bootstrapped before
        - Last bootstrap was > 6 months ago

        Returns:
            bool: True if bootstrap is needed
        """
        tracker_path = self._get_bootstrap_tracker_path()

        if not tracker_path.exists():
            return True

        try:
            with open(tracker_path, "r") as f:
                tracker = json.load(f)

            last_bootstrap = datetime.fromisoformat(tracker.get("last_bootstrap", ""))
            months_since = (datetime.utcnow() - last_bootstrap).days / 30

            if months_since >= 6:
                print(f"⏰ Last bootstrap was {months_since:.1f} months ago, re-bootstrap needed")
                return True

            print(f"✅ Bootstrap done {months_since:.1f} months ago, skipping")
            return False

        except Exception as e:
            print(f"⚠️  Error reading bootstrap tracker: {e}")
            return True  # If can't read, assume bootstrap needed

    def _mark_bootstrap_complete(self, patterns_loaded: int, projects: List[str]):
        """Mark bootstrap as complete."""
        tracker_path = self._get_bootstrap_tracker_path()
        tracker_path.parent.mkdir(parents=True, exist_ok=True)

        tracker = {
            "last_bootstrap": datetime.utcnow().isoformat(),
            "patterns_loaded": patterns_loaded,
            "projects": projects,
        }

        with open(tracker_path, "w") as f:
            json.dump(tracker, f, indent=2)

        print(f"✅ Bootstrap tracking updated: {patterns_loaded} patterns from {len(projects)} projects")

    def bootstrap_from_historical_patterns(
        self, patterns: List["HistoricalPattern"]
    ) -> int:
        """
        Pre-seed memory with historical patterns from resolved Sentry issues.

        This runs ONCE per 6 months to avoid reloading the same patterns.

        Args:
            patterns: List of HistoricalPattern objects from historical_loader

        Returns:
            Number of patterns successfully loaded
        """
        if not patterns:
            print("⚠️  No patterns to bootstrap")
            return 0

        print(f"\n🌱 Bootstrapping {len(patterns)} historical patterns...")

        loaded_count = 0
        skipped_count = 0
        failed_count = 0

        # Get existing patterns to check for duplicates
        existing_patterns = self._get_existing_pattern_signatures()

        for pattern in patterns:
            # Create a signature to check for duplicates
            signature = f"{pattern.error_type}:{pattern.fix_approach[:100]}"

            if signature in existing_patterns:
                skipped_count += 1
                continue

            # Store pattern
            try:
                if self.use_mock:
                    self._store_mock_historical_pattern(pattern)
                else:
                    self._store_mem0_historical_pattern(pattern)

                loaded_count += 1

            except Exception as e:
                print(f"⚠️  Failed to store pattern: {e}")
                failed_count += 1

        print(f"\n✨ Bootstrap complete:")
        print(f"   ✅ Loaded: {loaded_count}")
        print(f"   ⏭️  Skipped (duplicates): {skipped_count}")
        print(f"   ❌ Failed: {failed_count}")

        return loaded_count

    def _get_existing_pattern_signatures(self) -> set:
        """Get signatures of existing patterns to avoid duplicates."""
        signatures = set()

        if self.use_mock:
            for mem in self.mock_memories:
                if mem.get("category") == "error_pattern":
                    sig = f"{mem.get('error_type')}:{mem.get('fix_approach', '')[:100]}"
                    signatures.add(sig)
            return signatures

        try:
            # Get existing patterns from Mem0 using filters
            response = self.client.get_all(
                filters={"AND": [{"agent_id": self.agent_id}]},
                page_size=100
            )

            memories = []
            if isinstance(response, dict) and 'results' in response:
                memories = response['results']
            elif isinstance(response, list):
                memories = response

            for mem in memories:
                metadata = mem.get("metadata", {})
                if metadata.get("category") == "error_pattern":
                    error_type = metadata.get("error_type", "")
                    content = mem.get("memory", "")
                    sig = f"{error_type}:{content[:100]}"
                    signatures.add(sig)

        except Exception as e:
            print(f"⚠️  Could not check for duplicates: {e}")

        return signatures

    def _store_mem0_historical_pattern(self, pattern: "HistoricalPattern"):
        """Store a historical pattern in Mem0."""
        # Handle both github_pr_url and github_commit_url
        github_url = getattr(pattern, 'github_pr_url', None) or getattr(pattern, 'github_commit_url', None)

        metadata = {
            "category": "error_pattern",
            "error_type": pattern.error_type,
            "confidence": pattern.confidence,  # 0.95 for historical
            "status": "historical",
            "source": "bootstrap",
            "pr_url": github_url or "",
            "sentry_issue_id": pattern.sentry_issue_id,
            "occurrences": pattern.occurrences,
            "resolved_at": pattern.resolved_at.isoformat(),
            "project": pattern.project,
            "file_path": pattern.file_path or "",
            "function_name": pattern.function_name or "",
        }

        content = f"{pattern.error_type} in {pattern.function_name or 'unknown'}: {pattern.fix_approach}"

        print(f"   📝 Storing: {pattern.error_type} from {pattern.project}")
        result = self.client.add(
            messages=[{"role": "assistant", "content": content}],
            agent_id=self.agent_id,
            metadata=metadata,
        )
        print(f"      Result: {result}")

    def _store_mock_historical_pattern(self, pattern: "HistoricalPattern"):
        """Store a historical pattern in mock storage."""
        # Handle both github_pr_url and github_commit_url
        github_url = getattr(pattern, 'github_pr_url', None) or getattr(pattern, 'github_commit_url', None)

        memory = {
            "id": f"mock-historical-{len(self.mock_memories)}",
            "category": "error_pattern",
            "error_type": pattern.error_type,
            "fix_approach": pattern.fix_approach,
            "confidence": pattern.confidence,
            "status": "historical",
            "source": "bootstrap",
            "pr_url": github_url or "",
            "sentry_issue_id": pattern.sentry_issue_id,
            "occurrences": pattern.occurrences,
            "resolved_at": pattern.resolved_at.isoformat(),
            "project": pattern.project,
            "file_path": pattern.file_path or "",
            "function_name": pattern.function_name or "",
        }
        self.mock_memories.append(memory)
        print(f"✅ [MOCK] Stored historical pattern: {pattern.error_type} (now {len(self.mock_memories)} total)")


# Test the memory system
if __name__ == "__main__":
    print("🧪 Testing Memory System\n")

    memory = MemorySystem()

    # Test 1: Store pattern
    print("\n1. Storing pattern...")
    memory_id = memory.store_pattern(
        error_type="AttributeError",
        fix_approach="Add null check before accessing attribute",
        confidence=0.7,
    )

    # Test 2: Get all patterns
    print("\n2. Retrieving patterns...")
    patterns = memory.get_all_patterns()
    print(patterns)

    # Test 3: Update on PR merge
    print("\n3. Simulating PR merge...")
    memory.update_on_pr_merged(
        error_type="AttributeError",
        fix_approach="Add null check",
        pr_number=123,
    )

    # Test 4: Update on PR rejection
    print("\n4. Simulating PR rejection...")
    memory.update_on_pr_rejected(
        error_type="TypeError",
        fix_approach="Wrong type conversion",
        reason="Breaks existing tests",
        pr_number=124,
    )

    # Test 5: Get stats
    print("\n5. Getting stats...")
    stats = memory.get_stats()
    print(json.dumps(stats, indent=2))

    print("\n✅ All tests passed")
