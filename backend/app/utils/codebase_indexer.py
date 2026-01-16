# Codebase indexer - Index repository for RAG via GitHub API

import os
import ast
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
import chromadb
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound
from github import Github, Auth
from github.ContentFile import ContentFile

# Tree-sitter imports
from tree_sitter import Language, Parser

# Initialize tree-sitter parsers (lazy loading)
_ts_parsers = {}


def configure_gemini(api_key: Optional[str] = None):
    """Configure Gemini API."""
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)


def get_or_create_vector_db(persist_dir: str = "./data/chroma_db"):
    """Get or create ChromaDB collection for codebase."""
    os.makedirs(persist_dir, exist_ok=True)
    
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name="codebase",
        metadata={"description": "Indexed codebase for RAG"}
    )
    return collection


def fetch_repo_files(client: Github, owner: str, repo: str, path: str = "") -> List[Tuple[str, str]]:
    """
    Recursively fetch all code files from GitHub repository.
    
    Returns:
        List of tuples: (file_path, file_content)
    """
    files = []
    repo_obj = client.get_repo(f"{owner}/{repo}")
    
    def fetch_directory(dir_path: str):
        try:
            contents = repo_obj.get_contents(dir_path)
            
            # Handle single file
            if isinstance(contents, ContentFile):
                file_path = contents.path
                # Skip hidden files and common ignore patterns
                if any(part.startswith('.') for part in file_path.split('/')):
                    return
                if 'node_modules' in file_path or '__pycache__' in file_path:
                    return
                
                # Check if it's a code file using Pygments
                try:
                    get_lexer_for_filename(file_path)
                    # Decode content
                    content = base64.b64decode(contents.content).decode('utf-8')
                    files.append((file_path, content))
                except ClassNotFound:
                    # Not a code file, skip
                    pass
                except Exception:
                    # Error decoding, skip
                    pass
                return
            
            # Handle directory
            for item in contents:
                if item.type == "dir":
                    # Recursively fetch subdirectory
                    fetch_directory(item.path)
                elif item.type == "file":
                    file_path = item.path
                    # Skip hidden files and common ignore patterns
                    if any(part.startswith('.') for part in file_path.split('/')):
                        continue
                    if 'node_modules' in file_path or '__pycache__' in file_path:
                        continue
                    
                    # Check if it's a code file using Pygments
                    try:
                        get_lexer_for_filename(file_path)
                        # Decode content
                        content = base64.b64decode(item.content).decode('utf-8')
                        files.append((file_path, content))
                    except ClassNotFound:
                        # Not a code file, skip
                        pass
                    except Exception:
                        # Error decoding, skip
                        pass
        
        except Exception as e:
            print(f"Error fetching {dir_path}: {e}")
    
    fetch_directory(path)
    return files


def detect_language_from_path(file_path: str) -> Optional[str]:
    """Detect programming language from file path using Pygments."""
    try:
        lexer = get_lexer_for_filename(file_path)
        return lexer.name.lower()
    except ClassNotFound:
        return None


def _get_treesitter_parser(language: str) -> Optional[Parser]:
    """Get or create tree-sitter parser for a language."""
    if language in _ts_parsers:
        return _ts_parsers[language]
    
    try:
        lang = None
        if language == "javascript":
            from tree_sitter_javascript import language as js_lang
            lang = js_lang
        elif language == "typescript":
            from tree_sitter_typescript import language_typescript as ts_lang
            lang = ts_lang
        elif language == "java":
            from tree_sitter_java import language as java_lang
            lang = java_lang
        elif language == "cpp" or language == "c++":
            from tree_sitter_cpp import language as cpp_lang
            lang = cpp_lang
        elif language == "go":
            from tree_sitter_go import language as go_lang
            lang = go_lang
        
        if lang is None:
            return None
        
        parser = Parser(lang)
        _ts_parsers[language] = parser
        return parser
    except (ImportError, Exception) as e:
        # Silently fail if language package not available
        return None


def extract_python_units(file_path: str, content: str) -> List[Dict[str, str]]:
    """Extract code units from Python file using AST."""
    units = []
    
    try:
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                func_code = '\n'.join(content.split('\n')[start_line-1:end_line])
                
                units.append({
                    "code": func_code,
                    "type": "function",
                    "name": node.name,
                    "line_start": start_line,
                    "line_end": end_line
                })
            
            elif isinstance(node, ast.ClassDef):
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                class_code = '\n'.join(content.split('\n')[start_line-1:end_line])
                
                units.append({
                    "code": class_code,
                    "type": "class",
                    "name": node.name,
                    "line_start": start_line,
                    "line_end": end_line
                })
    except Exception:
        pass
    
    return units


def extract_treesitter_units(file_path: str, content: str, language: str) -> List[Dict[str, str]]:
    """Extract code units using tree-sitter."""
    units = []
    
    parser = _get_treesitter_parser(language)
    if not parser:
        return units
    
    try:
        tree = parser.parse(bytes(content, 'utf8'))
        root_node = tree.root_node
        
        # Language-specific query patterns
        queries = {
            "javascript": """
                (function_declaration name: (identifier) @name) @func
                (method_definition name: (property_identifier) @name) @func
                (class_declaration name: (identifier) @name) @class
            """,
            "typescript": """
                (function_declaration name: (identifier) @name) @func
                (method_definition name: (property_identifier) @name) @func
                (class_declaration name: (type_identifier) @name) @class
                (interface_declaration name: (type_identifier) @name) @interface
            """,
            "java": """
                (method_declaration name: (identifier) @name) @func
                (class_declaration name: (identifier) @name) @class
                (interface_declaration name: (identifier) @name) @interface
            """,
            "cpp": """
                (function_definition declarator: (function_declarator declarator: (identifier) @name)) @func
                (class_specifier name: (type_identifier) @name) @class
            """,
            "go": """
                (function_declaration name: (identifier) @name) @func
                (method_declaration name: (field_identifier) @name) @func
                (type_declaration (type_spec name: (type_identifier) @name)) @type
            """
        }
        
        query_str = queries.get(language)
        if not query_str:
            return units
        
        try:
            query = parser.language.query(query_str)
            captures = query.captures(root_node)
            
            # Build map of nodes to their names and types
            node_info = {}
            for node, capture_name in captures:
                node_id = id(node)
                if node_id not in node_info:
                    node_info[node_id] = {
                        "node": node,
                        "name": None,
                        "type": None
                    }
                
                if capture_name == "name":
                    node_info[node_id]["name"] = node.text.decode('utf8')
                elif capture_name in ["func", "class", "interface", "type"]:
                    node_info[node_id]["type"] = capture_name
            
            # Extract units
            for node_id, info in node_info.items():
                node = info["node"]
                name = info["name"]
                unit_type = info["type"]
                
                if not unit_type or not name:
                    continue
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                code = content[node.start_byte:node.end_byte]
                
                # Normalize type
                if unit_type == "func":
                    unit_type = "function"
                
                units.append({
                    "code": code,
                    "type": unit_type,
                    "name": name,
                    "line_start": start_line,
                    "line_end": end_line
                })
        except Exception:
            # If query parsing fails, fall back gracefully
            pass
    
    except Exception:
        pass
    
    return units


def extract_code_units(file_path: str, content: str) -> List[Dict[str, str]]:
    """Extract code units (functions, classes) from a code file."""
    units = []
    
    try:
        if not content.strip():
            return units
        
        language = detect_language_from_path(file_path)
        
        if language == "python":
            units = extract_python_units(file_path, content)
        elif language in ["javascript", "typescript", "java", "cpp", "c++", "go"]:
            # Normalize c++ to cpp
            if language == "c++":
                language = "cpp"
            units = extract_treesitter_units(file_path, content, language)
        
        # If no units extracted, fall back to whole file
        if not units:
            file_name = Path(file_path).name
            units.append({
                "code": content,
                "type": "file",
                "name": file_name
            })
    
    except Exception:
        # If everything fails, try to return whole file
        try:
            if content.strip():
                file_name = Path(file_path).name
                units.append({
                    "code": content,
                    "type": "file",
                    "name": file_name
                })
        except Exception:
            pass
    
    return units


def generate_embedding(code: str) -> List[float]:
    """Generate embedding for code using Gemini."""
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=code,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        raise ValueError(f"Failed to generate embedding: {e}")


def index_codebase(
    owner: str,
    repo: str,
    github_token: str,
    persist_dir: str = "./data/chroma_db",
    gemini_api_key: Optional[str] = None
):
    """
    Index codebase into vector database via GitHub API.
    
    Args:
        owner: Repository owner (username or org)
        repo: Repository name
        github_token: GitHub token for API access
        persist_dir: Directory to persist ChromaDB
        gemini_api_key: Gemini API key (optional, uses GEMINI_API_KEY env var if not provided)
    """
    print(f"Indexing repository: {owner}/{repo}")
    
    # Initialize GitHub client
    auth = Auth.Token(github_token)
    client = Github(auth=auth)
    
    # Initialize Gemini
    configure_gemini(gemini_api_key)
    
    # Get or create vector DB
    collection = get_or_create_vector_db(persist_dir)
    
    # Clear existing collection (for re-indexing) - only if it has data
    count = collection.count()
    if count > 0:
        print(f"Clearing existing index ({count} entries)...")
        # Delete all entries by getting all IDs first
        all_ids = collection.get()['ids']
        if all_ids:
            collection.delete(ids=all_ids)
    else:
        print("Creating new index...")
    
    # Fetch all code files from GitHub
    print("Fetching files from GitHub...")
    files = fetch_repo_files(client, owner, repo)
    print(f"Found {len(files)} code files")
    
    total_units = 0
    
    # Process each file
    for file_path, content in files:
        try:
            # Extract code units
            units = extract_code_units(file_path, content)
            
            for unit in units:
                code = unit["code"]
                
                # Skip very small units
                if len(code.strip()) < 50:
                    continue
                
                # Generate embedding
                embedding = generate_embedding(code)
                
                # Create unique ID
                unit_id = f"{file_path}:{unit['type']}:{unit['name']}"
                if 'line_start' in unit:
                    unit_id += f":{unit['line_start']}"
                
                # Get file extension for language
                file_ext = Path(file_path).suffix
                
                # Store in vector DB
                collection.add(
                    ids=[unit_id],
                    embeddings=[embedding],
                    documents=[code],
                    metadatas=[{
                        "file_path": file_path,
                        "type": unit["type"],
                        "name": unit["name"],
                        "language": file_ext,
                        "repo": f"{owner}/{repo}",
                        **({k: v for k, v in unit.items() if k in ['line_start', 'line_end']})
                    }]
                )
                
                total_units += 1
                
        except Exception as e:
            print(f"Error indexing {file_path}: {e}")
            continue
    
    print(f"Indexing complete! Indexed {total_units} code units")
    print(f"\nVector database stored at: {os.path.abspath(persist_dir)}")
    return collection



