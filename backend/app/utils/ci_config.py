# CI config detection - language detection and CI command inference

import os
import sys
import json
from typing import List, Optional

# Add backend directory to path for imports when running as script
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, backend_dir)

from pygments.lexers import get_lexer_for_filename
from app.models.context import FileChange, CIConfig


def detect_languages(file_changes: List[FileChange]) -> List[str]:
    """
    Detect programming languages from file extensions using Pygments.
    
    Args:
        file_changes: List of FileChange objects from PR
    
    Returns:
        List of detected language names (normalized, lowercase)
    """
    languages = set()
    
    for file_change in file_changes:
        try:
            # Pygments can detect language from filename/extension
            lexer = get_lexer_for_filename(file_change.path)
            # Normalize: "Python" -> "python", "TypeScript" -> "typescript"
            lang = lexer.name.lower()
            languages.add(lang)
        except:
            # Unknown extension, skip
            pass
    
    return sorted(list(languages))


def infer_ci_config_with_llm(languages: List[str], api_key: Optional[str] = None) -> CIConfig:
    """
    Use LLM to infer CI commands based on detected languages.
    
    Args:
        languages: List of detected programming languages
        api_key: OpenAI API key (or reads from OPENAI_API_KEY env var)
    
    Returns:
        CIConfig with inferred test/lint/build commands
    """
    if not languages:
        return CIConfig(languages=[], test_command=None, lint_command=None, build_command=None)
    
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        # Fallback to simple rules if no API key
        return _infer_ci_config_simple(languages)
    
    # Build prompt for LLM
    languages_str = ", ".join(languages)
    prompt = f"""Given the following programming languages detected in a repository: {languages_str}

Suggest appropriate CI commands. Return ONLY valid JSON in this exact format:
{{
    "test_command": "command here or null",
    "lint_command": "command here or null",
    "build_command": "command here or null"
}}

If multiple languages, combine commands (e.g., "npm test && pytest").
If a command is not applicable, use null."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for simple tasks
            messages=[
                {"role": "system", "content": "You are a helpful assistant that suggests CI commands. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        # Extract JSON from response
        content = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        # Parse JSON
        config_data = json.loads(content)
        
        return CIConfig(
            languages=languages,
            test_command=config_data.get("test_command"),
            lint_command=config_data.get("lint_command"),
            build_command=config_data.get("build_command")
        )
    except Exception as e:
        print(f"Error calling LLM: {e}")
        # Fallback to simple rules
        return _infer_ci_config_simple(languages)


def _infer_ci_config_simple(languages: List[str]) -> CIConfig:
    """
    Simple fallback: infer CI commands from languages using basic rules.
    """
    test_commands = []
    lint_commands = []
    build_commands = []
    
    for lang in languages:
        if lang == "python":
            test_commands.append("pytest")
            lint_commands.append("ruff check .")
        elif lang in ["typescript", "javascript"]:
            test_commands.append("npm test")
            lint_commands.append("npm run lint")
            build_commands.append("tsc --noEmit")
        elif lang == "java":
            test_commands.append("mvn test")
            lint_commands.append("mvn checkstyle:check")
        elif lang == "go":
            test_commands.append("go test ./...")
            lint_commands.append("golangci-lint run")
        elif lang == "rust":
            test_commands.append("cargo test")
            lint_commands.append("cargo clippy")
    
    # Combine commands if multiple languages
    test_cmd = " && ".join(test_commands) if test_commands else None
    lint_cmd = " && ".join(lint_commands) if lint_commands else None
    build_cmd = " && ".join(build_commands) if build_commands else None
    
    return CIConfig(
        languages=languages,
        test_command=test_cmd,
        lint_command=lint_cmd,
        build_command=build_cmd
    )


# if __name__ == "__main__":
#     # Test using output from diff_parser
#     from app.utils.github_api import get_github_client, get_pr, get_pr_diff
#     from app.utils.diff_parser import parse_diff
    
#     TOKEN = os.getenv("GITHUB_TOKEN")
#     client = get_github_client(TOKEN)
    
#     # Get a PR
#     pr = get_pr(client, "Azielll", "shop-comp", 1)
    
#     # Get and parse the diff
#     diff_text = get_pr_diff(pr, TOKEN)
#     file_changes = parse_diff(diff_text)
    
#     print(f"Found {len(file_changes)} file(s) changed\n")
    
#     # Detect languages
#     languages = detect_languages(file_changes)
#     print(f"Detected languages: {', '.join(languages) if languages else 'None'}\n")
    
#     # Infer CI config
#     ci_config = infer_ci_config_with_llm(languages)
    
#     print("CI Config:")
#     print(f"  Languages: {ci_config.languages}")
#     print(f"  Test command: {ci_config.test_command}")
#     print(f"  Lint command: {ci_config.lint_command}")
#     print(f"  Build command: {ci_config.build_command}")

