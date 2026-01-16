#!/usr/bin/env python3
"""
Simple test script for codebase indexer via GitHub API.

Usage:
    export GITHUB_TOKEN=your_token
    export GEMINI_API_KEY=your_key
    python test_indexer.py owner repo
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.utils.codebase_indexer import index_codebase, get_or_create_vector_db


def main():
    """Test the codebase indexer with GitHub API."""
    
    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Set it with: export GITHUB_TOKEN=your_token")
        sys.exit(1)
    
    if not gemini_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Set it with: export GEMINI_API_KEY=your_key")
        sys.exit(1)
    
    # Get repo from command line
    if len(sys.argv) < 3:
        print("Usage: python test_indexer.py <owner> <repo>")
        print("\nExample:")
        print("  python test_indexer.py microsoft vscode")
        print("  python test_indexer.py facebook react")
        sys.exit(1)
    
    owner = sys.argv[1]
    repo = sys.argv[2]
    
    print(f"\n{'='*60}")
    print(f"Testing Codebase Indexer")
    print(f"{'='*60}")
    print(f"Repository: {owner}/{repo}")
    print(f"GitHub Token: {'*' * 20}...{github_token[-4:] if len(github_token) > 4 else '****'}")
    print(f"Gemini Key: {'*' * 20}...{gemini_key[-4:] if len(gemini_key) > 4 else '****'}")
    print(f"{'='*60}\n")
    
    # Index the repository
    try:
        persist_dir = f"./data/chroma_db_{owner}_{repo}"
        
        print("Starting indexing process...")
        collection = index_codebase(
            owner=owner,
            repo=repo,
            github_token=github_token,
            persist_dir=persist_dir,
            gemini_api_key=gemini_key
        )
        
        # Show results
        count = collection.count()
        print(f"\n{'='*60}")
        print(f"✓ Indexing Complete!")
        print(f"{'='*60}")
        print(f"Total code units indexed: {count}")
        print(f"Vector database location: {os.path.abspath(persist_dir)}")
        
        # Show sample entries
        if count > 0:
            print(f"\nSample entries (first 3):")
            results = collection.get(limit=3)
            for i, (id, metadata, doc) in enumerate(zip(
                results['ids'],
                results['metadatas'],
                results['documents']
            ), 1):
                file_path = metadata.get('file_path', 'unknown')
                unit_type = metadata.get('type', 'unknown')
                name = metadata.get('name', 'unknown')
                print(f"\n  {i}. {file_path}")
                print(f"     Type: {unit_type}, Name: {name}")
                print(f"     Preview: {doc[:80]}...")
        
        print(f"\n{'='*60}\n")
        
    except Exception as e:
        print(f"\n✗ Error during indexing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
