# Context collector - gathers PR context from GitHub

from typing import Optional
from app.models.context import Context, PRMetadata, CIConfig
from app.utils.github_api import get_github_client, get_pr, get_pr_metadata, get_pr_diff
from app.utils.diff_parser import parse_diff
from app.utils.ci_config import detect_languages, infer_ci_config_with_llm


def collect_context(
    owner: str,
    repo: str,
    pr_number: int,
    token: Optional[str] = None
) -> Context:
    """
    Collect complete PR context for code review.
    
    Args:
        owner: Repository owner (username or org)
        repo: Repository name
        pr_number: Pull request number
        token: GitHub token (optional, uses GITHUB_TOKEN env var if not provided)
    
    Returns:
        Context object with PR metadata, file changes, CI config, and raw diff
    """
    # 1. Get GitHub client and PR
    client = get_github_client(token)
    pr = get_pr(client, owner, repo, pr_number)
    
    # 2. Get PR metadata
    metadata = get_pr_metadata(pr)
    
    # 3. Get PR diff
    diff_text = get_pr_diff(pr, token)
    
    # 4. Parse diff into FileChange objects
    file_changes = parse_diff(diff_text)
    
    # 5. Detect languages from file changes
    languages = detect_languages(file_changes)
    
    # 6. Infer CI config from languages
    ci_config = infer_ci_config_with_llm(languages)
    
    # 7. Build PRMetadata model
    pr_metadata = PRMetadata(
        title=metadata["title"],
        description=metadata["description"],
        labels=metadata["labels"],
        author=metadata["author"],
        base_branch=metadata["base_branch"],
        target_branch=metadata["target_branch"]
    )
    
    # 8. Build and return Context
    return Context(
        pr_metadata=pr_metadata,
        file_changes=file_changes,
        ci_config=ci_config,
        diff_text=diff_text
    )

