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


# RAG-related models
class CodePattern(BaseModel):
    """A similar code pattern found in the codebase via RAG."""
    file_path: str
    code_snippet: str
    similarity_score: float
    description: str  # What pattern this represents


class BestPractice(BaseModel):
    """A best practice or guideline retrieved from documentation."""
    source: str  # e.g., "docs/coding-standards.md" or "ARCHITECTURE.md"
    content: str
    relevance: str  # Why this is relevant to the PR


class RelatedFile(BaseModel):
    """A file related to the PR changes (imports, tests, docs, etc.)."""
    path: str
    relationship: str  # e.g., "imports", "used_by", "test_file", "documentation"
    reason: str  # Why this file is relevant


class RetrievedKnowledge(BaseModel):
    """Knowledge retrieved from codebase via RAG."""
    similar_patterns: List[CodePattern] = []
    best_practices: List[BestPractice] = []
    related_files: List[RelatedFile] = []


class Context(BaseModel):
    """Complete context about a PR for code review."""
    pr_metadata: PRMetadata
    file_changes: List[FileChange] = []
    ci_config: CIConfig
    diff_text: str  # Raw diff string for LLM prompts
    retrieved_knowledge: Optional[RetrievedKnowledge] = None  # RAG-retrieved context
