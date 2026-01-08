# Diff parser - parse PR diffs and convert to models

import os
import sys
import re
from typing import List

# Add backend directory to path for imports when running as script
# This allows imports like "from app.models.context import ..." to work
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, backend_dir)

from app.models.context import FileChange, DiffHunk
from app.utils.github_api import get_github_client, get_pr, get_pr_diff


def parse_diff(diff_text: str) -> List[FileChange]:
    """
    Parse a unified diff string and extract file changes with hunks.
    
    Args:
        diff_text: Raw diff string from GitHub API
    
    Returns:
        List of FileChange objects with parsed hunks
    """
    if not diff_text or not diff_text.strip():
        return []
    
    file_changes = []
    sections = diff_text.split('diff --git')
    
    # Skip first empty section (everything before first diff --git)
    for section in sections[1:]:
        if not section.strip():
            continue
        
        file_change = _parse_file_section(section)
        if file_change:
            file_changes.append(file_change)
    
    return file_changes


def _parse_file_section(section: str) -> FileChange:
    """Parse a single file section from the diff."""
    lines = section.split('\n')
    
    # Extract file path from +++ line
    file_path = None
    for line in lines:
        if line.startswith('+++'):
            # Extract path: "+++ b/path/to/file" -> "path/to/file"
            path = line[4:].strip().split('\t')[0]
            if path.startswith('b/'):
                file_path = path[2:]
            elif path != '/dev/null':
                file_path = path
            break
    
    # Fallback: try to extract from diff --git line (if present)
    if not file_path:
        for line in lines:
            if 'b/' in line:
                match = re.search(r'b/([^\s]+)', line)
                if match:
                    file_path = match.group(1)
                    break
    
    if not file_path or file_path == '/dev/null':
        return None
    
    # Find all hunks (@@ lines)
    hunks = []
    i = 0
    while i < len(lines):
        if lines[i].startswith('@@'):
            hunk = _parse_hunk(lines, i)
            if hunk:
                hunks.append(hunk)
                # Skip to end of hunk
                i = _find_hunk_end(lines, i + 1)
            else:
                i += 1
        else:
            i += 1
    
    # Count additions (+) and deletions (-)
    additions = 0
    deletions = 0
    for hunk in hunks:
        for line in hunk.content.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
    
    return FileChange(
        path=file_path,
        additions=additions,
        deletions=deletions,
        hunks=hunks
    )


def _parse_hunk(lines: List[str], hunk_start: int) -> DiffHunk:
    """Parse a single hunk from the diff."""
    if hunk_start >= len(lines):
        return None
    
    header = lines[hunk_start]
    
    # Parse hunk header: "@@ -old_start,old_lines +new_start,new_lines @@"
    match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
    if not match:
        return None
    
    old_start = int(match.group(1))
    old_lines = int(match.group(2) or 1)
    new_start = int(match.group(3))
    new_lines = int(match.group(4) or 1)
    
    # Collect hunk content until next @@ or end
    content_lines = [header]
    for i in range(hunk_start + 1, len(lines)):
        line = lines[i]
        if line.startswith('@@'):
            break
        content_lines.append(line)
    
    content = '\n'.join(content_lines)
    
    return DiffHunk(
        old_start=old_start,
        old_lines=old_lines,
        new_start=new_start,
        new_lines=new_lines,
        content=content
    )


def _find_hunk_end(lines: List[str], start: int) -> int:
    """Find the end of current hunk (next @@ or end of section)."""
    for i in range(start, len(lines)):
        if lines[i].startswith('@@'):
            return i
    return len(lines)



# if __name__ == "__main__":
#     # Test the diff parser using GitHub API
#     TOKEN = os.getenv("GITHUB_TOKEN")
#     client = get_github_client(TOKEN)
    
#     # Get a PR
#     pr = get_pr(client, "Azielll", "shop-comp", 1)
    
#     # Get the diff
#     diff_text = get_pr_diff(pr, TOKEN)
    
#     # Parse the diff
#     file_changes = parse_diff(diff_text)
    
#     # Print results
#     print(f"Found {len(file_changes)} file(s) changed:")
#     print()
    
#     for file_change in file_changes:
#         print(f"File: {file_change.path}")
#         print(f"  Additions: {file_change.additions}")
#         print(f"  Deletions: {file_change.deletions}")
#         print(f"  Hunks: {len(file_change.hunks)}")
        
#         for i, hunk in enumerate(file_change.hunks, 1):
#             print(f"    Hunk {i}:")
#             print(f"      Old: lines {hunk.old_start}-{hunk.old_start + hunk.old_lines - 1} ({hunk.old_lines} lines)")
#             print(f"      New: lines {hunk.new_start}-{hunk.new_start + hunk.new_lines - 1} ({hunk.new_lines} lines)")
        
#         print()