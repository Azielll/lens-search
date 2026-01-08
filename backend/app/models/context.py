# Context data models - PR metadata, file changes, CI config

from typing import List, Optional
from pydantic import BaseModel


class DiffHunk(BaseModel):
    """A single contiguous block of changes in a file."""
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str  # The actual diff content with +, -, and context lines


class FileChange(BaseModel):
    """Summary of changes to a single file in the PR."""
    path: str
    additions: int = 0
    deletions: int = 0
    hunks: List[DiffHunk] = []


class CIConfig(BaseModel):
    """Detected languages and available tools/commands in the repo."""
    languages: List[str] = []
    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    build_command: Optional[str] = None


class PRMetadata(BaseModel):
    """High-level information about the PR."""
    title: str
    description: str = ""
    labels: List[str] = []
    author: str
    base_branch: str
    target_branch: str


class Context(BaseModel):
    """Complete context about a PR for code review."""
    pr_metadata: PRMetadata
    file_changes: List[FileChange] = []
    ci_config: CIConfig
    diff_text: str  # Raw diff string for LLM prompts
