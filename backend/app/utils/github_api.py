# GitHub API client - minimal client for fetching PR data

import os
from typing import Optional
from github import Github, Auth
from github.PullRequest import PullRequest


def get_github_client(token: Optional[str] = None) -> Github:
    """
    Create and return a GitHub API client.
    
    Args:
        token: GitHub Personal Access Token. If None, reads from GITHUB_TOKEN env var.
    
    Returns:
        Authenticated Github client instance.
    """
    if token is None:
        token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        raise ValueError("GitHub token not provided. Set GITHUB_TOKEN env var or pass token parameter.")
    
    # Use Auth.Token() to avoid deprecation warning
    auth = Auth.Token(token)
    return Github(auth=auth)


def get_pr(client: Github, owner: str, repo: str, pr_number: int) -> PullRequest:
    """
    Fetch a pull request from GitHub.
    
    Args:
        client: Authenticated Github client instance
        owner: Repository owner (username or org)
        repo: Repository name
        pr_number: Pull request number
    
    Returns:
        PullRequest object with PR data
    
    Raises:
        ValueError: If PR not found or repo doesn't exist
    """
    try:
        repository = client.get_repo(f"{owner}/{repo}")
        pr = repository.get_pull(pr_number)
        return pr
    except Exception as e:
        print(f"Error fetching PR #{pr_number} from {owner}/{repo}: {e}")
        raise


def get_pr_diff(pr: PullRequest, token: Optional[str] = None) -> str:
    """
    Fetch the raw diff for a pull request.
    
    Args:
        pr: PullRequest object from get_pr()
        token: GitHub token. If None, reads from GITHUB_TOKEN env var.
    
    Returns:
        Raw diff string in unified diff format
    """
    import requests
    
    if token is None:
        token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        raise ValueError("GitHub token required to fetch PR diff.")
    
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"token {token}",
    }
    
    # Extract repo info from PR object
    repo_full_name = pr.base.repo.full_name  # e.g., "owner/repo"
    pr_number = pr.number
    
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching PR diff: {response.status_code} - {response.text}")
        raise ValueError(f"Failed to fetch PR diff: {response.status_code}")
    
    return response.text


def get_pr_metadata(pr: PullRequest) -> dict:
    """
    Fetch PR metadata as a dictionary.
    
    Args:
        pr: PullRequest object from get_pr()
    
    Returns:
        Dictionary with PR metadata:
        - title: str
        - description: str (body)
        - labels: List[str]
        - author: str
        - base_branch: str
        - target_branch: str
        - number: int
    """
    return {
        "title": pr.title or "",
        "description": pr.body or "",
        "labels": [label.name for label in pr.labels],
        "author": pr.user.login if pr.user else "",
        "base_branch": pr.base.ref,
        "target_branch": pr.head.ref,
        "number": pr.number,
    }



# if __name__ == "__main__":
#     # Get token from environment variable
#     # Set it with: export GITHUB_TOKEN=your_token_here
#     TOKEN = os.getenv("GITHUB_TOKEN")
#     client = get_github_client(TOKEN)
#     PR = get_pr(client, "AzieLll", "shop-comp", 1)
    
#     # Get metadata using the new function
#     metadata = get_pr_metadata(PR)
#     print(metadata)
    
#     # Get diff using the new function
#     diff = get_pr_diff(PR, TOKEN)
#     print(diff)
#     print(f"Diff length: {len(diff)} characters")