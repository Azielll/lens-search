# Knowledge retriever - RAG retrieval from indexed codebase

import os
from typing import List, Optional
from app.models.context import (
    Context, 
    FileChange, 
    RetrievedKnowledge, 
    CodePattern, 
    BestPractice, 
    RelatedFile
)
from app.utils.codebase_indexer import get_or_create_vector_db, generate_embedding, configure_gemini


def retrieve_similar_patterns(
    file_changes: List[FileChange],
    persist_dir: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7,
    gemini_api_key: Optional[str] = None
) -> List[CodePattern]:
    """
    Retrieve similar code patterns from indexed codebase.
    
    Args:
        file_changes: List of file changes from PR
        persist_dir: Directory where vector DB is stored
        top_k: Number of similar patterns to retrieve per file
        similarity_threshold: Minimum similarity score
        gemini_api_key: Gemini API key for embeddings
    
    Returns:
        List of similar code patterns
    """
    patterns = []
    
    # Configure Gemini for embeddings
    configure_gemini(gemini_api_key)
    
    # Get vector DB collection
    collection = get_or_create_vector_db(persist_dir)
    
    # Extract code from each changed file
    for file_change in file_changes:
        # Get code snippets from diff hunks
        for hunk in file_change.hunks:
            # Extract the code from the hunk (lines that were added)
            code_lines = []
            for line in hunk.content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    code_lines.append(line[1:])  # Remove '+' prefix
            
            if not code_lines:
                continue
            
            code_snippet = '\n'.join(code_lines)
            if len(code_snippet.strip()) < 50:
                continue
            
            # Generate embedding for the code snippet
            try:
                query_embedding = generate_embedding(code_snippet)
            except Exception:
                continue
            
            # Query vector DB for similar patterns
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where={"repo": file_change.path.split('/')[0] + "/" + file_change.path.split('/')[1]} if '/' in file_change.path else None
                )
                
                # Process results
                if results['ids'] and len(results['ids'][0]) > 0:
                    for i, (id, distance, document, metadata) in enumerate(zip(
                        results['ids'][0],
                        results['distances'][0],
                        results['documents'][0],
                        results['metadatas'][0]
                    )):
                        # Convert distance to similarity score (1 - distance for cosine similarity)
                        similarity = 1 - distance
                        
                        if similarity >= similarity_threshold:
                            # Skip if it's the same file being changed
                            if metadata.get('file_path') == file_change.path:
                                continue
                            
                            patterns.append(CodePattern(
                                file_path=metadata.get('file_path', ''),
                                code_snippet=document,
                                similarity_score=similarity,
                                description=f"Similar {metadata.get('type', 'code')} '{metadata.get('name', 'unknown')}' found in codebase"
                            ))
            
            except Exception:
                continue
    
    # Sort by similarity score (highest first)
    patterns.sort(key=lambda x: x.similarity_score, reverse=True)
    
    # Remove duplicates and limit to top results
    seen = set()
    unique_patterns = []
    for pattern in patterns:
        key = (pattern.file_path, pattern.code_snippet[:100])  # Use first 100 chars as key
        if key not in seen:
            seen.add(key)
            unique_patterns.append(pattern)
            if len(unique_patterns) >= top_k * 3:  # Get more to account for filtering
                break
    
    return unique_patterns[:top_k * 2]  # Return top 2x for variety


def retrieve_related_files(
    file_changes: List[FileChange],
    persist_dir: str
) -> List[RelatedFile]:
    """
    Find related files based on similar names.
    
    Args:
        file_changes: List of file changes from PR
        persist_dir: Directory where vector DB is stored
    
    Returns:
        List of related files
    """
    related_files = []
    
    try:
        collection = get_or_create_vector_db(persist_dir)
        
        for file_change in file_changes:
            file_path = file_change.path
            file_name = os.path.basename(file_path)
            
            # Query for files with similar names
            try:
                results = collection.get(
                    where={"file_path": {"$contains": file_name}},
                    limit=10
                )
                
                for metadata in results.get('metadatas', []):
                    related_path = metadata.get('file_path', '')
                    
                    # Skip the file being changed
                    if related_path == file_path:
                        continue
                    
                    related_files.append(RelatedFile(
                        path=related_path,
                        relationship="similar_name",
                        reason=f"File name matches {file_name}"
                    ))
            
            except Exception:
                continue
    
    except Exception:
        pass
    
    # Remove duplicates
    seen = set()
    unique_files = []
    for rf in related_files:
        if rf.path not in seen:
            seen.add(rf.path)
            unique_files.append(rf)
    
    return unique_files[:10]  # Limit to 10 related files


def retrieve_knowledge(
    context: Context,
    persist_dir: str,
    gemini_api_key: Optional[str] = None
) -> RetrievedKnowledge:
    """
    Retrieve knowledge from indexed codebase using RAG.
    
    Args:
        context: Context object with PR information
        persist_dir: Directory where vector DB is stored
        gemini_api_key: Gemini API key for embeddings
    
    Returns:
        RetrievedKnowledge object with similar patterns and related files
    """
    similar_patterns = retrieve_similar_patterns(
        file_changes=context.file_changes,
        persist_dir=persist_dir,
        gemini_api_key=gemini_api_key
    )
    
    related_files = retrieve_related_files(
        file_changes=context.file_changes,
        persist_dir=persist_dir
    )
    
    return RetrievedKnowledge(
        similar_patterns=similar_patterns,
        best_practices=[],  # TODO: Implement best practices retrieval
        related_files=related_files
    )
