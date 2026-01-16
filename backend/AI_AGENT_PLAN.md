# AI Agent Code Review - Implementation Plan

## Overview
This document outlines the plan for building the AI agent component that reviews GitHub pull requests. We're focusing on the core AI logic first, deferring frontend and infrastructure integration.

---

## 1. Architecture Overview

### Core Components
```
backend/app/
├── agents/
│   ├── __init__.py
│   ├── planner.py          # Step 2: Planning agent
│   ├── reviewer.py         # Step 4: Review generation agent
│   └── fixer.py            # Step 5: Auto-fix agent (future)
├── services/
│   ├── context_collector.py    # Step 1: Collect PR context
│   ├── knowledge_retriever.py  # Step 1.5: RAG - Retrieve codebase patterns
│   ├── tool_runner.py          # Step 3: Execute lint/test tools
│   ├── review_formatter.py     # Format structured reviews
│   └── safety_checker.py       # Step 6: Safety/guardrails
├── models/
│   ├── review.py           # Pydantic models for review structure
│   ├── plan.py             # Pydantic models for agent plans
│   └── context.py          # Pydantic models for PR context
└── utils/
    ├── github_api.py       # GitHub API client (minimal, for testing)
    ├── diff_parser.py      # Parse diffs and extract hunks
    ├── prompt_templates.py # LLM prompt templates
    └── codebase_indexer.py # Index codebase for RAG (embeddings, vector DB)
```

---

## 2. Core AI Agent Components

### 2.1 Context Collector (`services/context_collector.py`)
**Purpose**: Step 1 - Gather all necessary context for the agent

**Responsibilities**:
- Parse PR diff (files changed, hunks, line numbers)
- Extract repository metadata:
  - Detected languages (from file extensions)
  - Existing CI configs (.github/workflows, package.json, requirements.txt, etc.)
  - Test/lint commands inferred from configs
- Collect PR metadata:
  - Title, description, labels
  - Author, reviewers
  - Base/target branches
- Fetch existing CI status (if available via GitHub API)
- Structure data into `Context` model

**Input**: PR webhook payload or manual trigger payload
**Output**: `Context` model (structured data ready for agent)

**Key Functions**:
- `collect_pr_context(pr_data: dict) -> Context`
- `parse_diff(diff_text: str) -> List[FileChange]`
- `detect_languages(files: List[str]) -> List[str]`
- `infer_ci_commands(repo_config: dict) -> CIConfig`

---

### 2.1.5 Knowledge Retriever (`services/knowledge_retriever.py`)
**Purpose**: Step 1.5 - Retrieve relevant codebase patterns and knowledge using RAG

**Responsibilities**:
- Retrieve similar code patterns from the codebase (functions, classes, modules)
- Find project-specific best practices and architectural patterns
- Identify related files that might be affected by PR changes
- Access documentation, style guides, and coding standards
- Provide contextual knowledge to enhance review quality

**RAG Pipeline**:
1. **Indexing** (one-time or periodic):
   - Generate embeddings for all source code files
   - Index documentation files (docs/, README.md, ARCHITECTURE.md)
   - Index test files to understand testing patterns
   - Store embeddings in vector database

2. **Retrieval** (on-demand during PR review):
   - For each changed function/class: retrieve top-K similar implementations
   - For changed APIs: retrieve related documentation and test patterns
   - For architectural changes: retrieve architectural guidelines and patterns
   - Filter and rank retrieved results by relevance

3. **Context Enhancement**:
   - Format retrieved code patterns for LLM consumption
   - Include file paths and line numbers for reference
   - Provide summaries of coding conventions found

**Retrieval Strategies**:
- **Semantic Search**: Use code embeddings to find functionally similar code
- **Pattern Matching**: Find code following similar patterns (same module, same interface)
- **Dependency Analysis**: Find files that import/use changed files
- **Documentation Lookup**: Retrieve relevant docs based on changed functionality

**Input**: `Context` model (file changes, diff text)
**Output**: `RetrievedKnowledge` model (similar patterns, best practices, related files)

**Key Functions**:
- `retrieve_similar_patterns(file_change: FileChange) -> List[CodePattern]`
- `retrieve_best_practices(context: Context) -> List[BestPractice]`
- `retrieve_related_files(file_changes: List[FileChange]) -> List[RelatedFile]`
- `retrieve_architectural_patterns(context: Context) -> List[ArchPattern]`
- `index_codebase(repo_path: str) -> None` (one-time setup)

**Example Use Cases**:
- Reviewing `authenticate_user()` → Retrieve other auth functions to check consistency
- Adding API endpoint → Retrieve API documentation and test patterns
- Creating service class → Retrieve existing service patterns and architecture docs
- Changing import → Find all usages of that import to check for breaking changes

---

### 2.2 Planning Agent (`agents/planner.py`)
**Purpose**: Step 2 - Generate a focused review plan based on context

**Responsibilities**:
- Analyze context (diff size, file types, PR description)
- Generate structured plan using LLM:
  - List of review tasks (e.g., "Check correctness in changed functions")
  - Prioritization (must-fix vs should-fix vs nice-to-have areas)
  - Tool selection (which linters/tests to run)
- Apply safety rules:
  - If diff is huge (>1000 lines), focus on high-risk files only
  - Skip review if PR is marked as "draft" or specific labels

**LLM Prompt Structure**:
```
You are a code review planning agent. Given:
- PR diff (files changed, hunks)
- Repository languages: {languages}
- Available tools: {tools}
- PR metadata: {title, description}
- Retrieved codebase patterns: {similar_patterns}
- Related files: {related_files}

Generate a focused review plan:
1. Which areas to check (correctness, security, performance, style, consistency)
2. Which tools to run (eslint, tsc, pytest, ruff, etc.)
3. Priority level (must-fix vs should-fix vs nice-to-have)
4. Areas to check for consistency with existing codebase patterns

Output JSON:
{
  "tasks": [
    {"type": "correctness", "scope": "changed_functions", "priority": "must"},
    {"type": "security", "scope": "all", "priority": "must"},
    ...
  ],
  "tools": ["eslint", "tsc"],
  "focus_files": ["path/to/file.py"]  # if diff is huge
}
```

**Input**: `Context` model, `RetrievedKnowledge` (from RAG)
**Output**: `ReviewPlan` model (structured plan)

**Key Functions**:
- `create_plan(context: Context) -> ReviewPlan`
- `should_review(context: Context) -> bool` (safety check)

---

### 2.3 Tool Runner (`services/tool_runner.py`)
**Purpose**: Step 3 - Execute linting/testing tools based on plan

**Responsibilities**:
- Run tools specified in plan (eslint, tsc, pytest, ruff, etc.)
- Parse tool output (errors, warnings, test failures)
- Map results back to specific files/lines from the diff
- Handle tool failures gracefully (if tool not installed, skip)
- Support both local execution (for testing) and GitHub Actions environment

**Tool Execution Strategy**:
- Run tools in isolated subprocesses
- Parse stdout/stderr for structured output
- Timeout handling (tools shouldn't hang)
- Cache results when possible

**Supported Tools** (initially):
- **TypeScript/JavaScript**: `eslint`, `tsc --noEmit`
- **Python**: `ruff`, `mypy`, `pytest`
- **Optional**: `semgrep` (security rules)

**Input**: `ReviewPlan`, `Context` (for file paths)
**Output**: `ToolResults` model (structured tool outputs)

**Key Functions**:
- `run_tools(plan: ReviewPlan, context: Context) -> ToolResults`
- `run_eslint(file_paths: List[str]) -> List[LintError]`
- `run_tsc(file_paths: List[str]) -> List[TypeError]`
- `run_ruff(file_paths: List[str]) -> List[LintError]`
- `run_pytest(test_paths: List[str]) -> TestResults`
- `parse_tool_output(tool: str, stdout: str, stderr: str) -> List[Issue]`

---

### 2.4 Review Agent (`agents/reviewer.py`)
**Purpose**: Step 4 - Generate structured review comments from tool results

**Responsibilities**:
- Analyze tool results + original diff
- Generate review comments using LLM:
  - Map tool errors to specific code locations
  - Add contextual explanations (why it's a problem)
  - Suggest fixes (code snippets)
  - Categorize by priority: ✅ Must-fix, ⚠️ Should-fix, 💡 Nice-to-have
- Ensure comments point to specific file/line or diff hunks
- Format output as structured review

**LLM Prompt Structure**:
```
You are a code review agent. Given:
- PR diff (with file/line context)
- Tool results: {tool_results}
- Review plan: {plan}
- Similar codebase patterns: {similar_patterns}
- Project best practices: {best_practices}
- Related files: {related_files}

Generate structured review comments:

For each issue found:
1. Category: must-fix / should-fix / nice-to-have
2. File + line number or diff hunk
3. Issue description
4. Suggested fix (if applicable)

Output JSON:
{
  "must_fix": [
    {
      "file": "src/app.py",
      "line": 42,
      "type": "bug",
      "description": "...",
      "suggestion": "...",
      "diff_hunk": "..."  // if applicable
    }
  ],
  "should_fix": [...],
  "nice_to_have": [...]
}
```

**Input**: `ToolResults`, `Context`, `ReviewPlan`, `RetrievedKnowledge` (from RAG)
**Output**: `Review` model (structured review with categorized comments)

**Key Functions**:
- `generate_review(tool_results: ToolResults, context: Context, plan: ReviewPlan) -> Review`
- `categorize_issue(issue: Issue, context: Context) -> str` (must/should/nice)
- `format_comment(issue: Issue) -> ReviewComment`

---

### 2.5 Review Formatter (`services/review_formatter.py`)
**Purpose**: Format structured review into GitHub comment format

**Responsibilities**:
- Convert `Review` model to GitHub PR comment format
- Format as markdown with emojis (✅ ⚠️ 💡)
- Include code blocks for suggestions
- Add file/line references (can be clicked in GitHub UI)
- Group comments by file

**Input**: `Review` model
**Output**: Formatted markdown string (or GitHub API payload)

**Key Functions**:
- `format_review(review: Review) -> str` (markdown)
- `format_for_github_api(review: Review) -> dict` (GitHub API format)

---

### 2.6 Safety Checker (`services/safety_checker.py`)
**Purpose**: Step 6 - Apply guardrails to prevent annoying/inaccurate reviews

**Responsibilities**:
- Check if diff is too large → only review high-risk files
- Check if tests failed for unrelated reasons → comment-only mode
- Verify coverage/certainty before auto-fixing
- Skip review if PR has certain labels ("skip-review", "draft")
- Rate limiting (don't spam if agent is triggered multiple times)

**Key Functions**:
- `should_review_pr(context: Context) -> Tuple[bool, str]` (bool + reason)
- `is_diff_too_large(context: Context, threshold: int = 1000) -> bool`
- `is_high_risk_file(file_path: str) -> bool`
- `should_auto_fix(review: Review) -> bool`

---

## 3. Data Models (`models/`)

### 3.1 `models/context.py`
```python
@dataclass
class FileChange:
    path: str
    additions: int
    deletions: int
    hunks: List[DiffHunk]

@dataclass
class DiffHunk:
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str

@dataclass
class CIConfig:
    languages: List[str]
    test_command: Optional[str]
    lint_command: Optional[str]
    build_command: Optional[str]

@dataclass
class PRMetadata:
    title: str
    description: str
    labels: List[str]
    author: str
    base_branch: str
    target_branch: str

@dataclass
class CodePattern:
    file_path: str
    code_snippet: str
    similarity_score: float
    description: str  # What pattern this represents

@dataclass
class BestPractice:
    source: str  # "docs/coding-standards.md" or "ARCHITECTURE.md"
    content: str
    relevance: str  # Why this is relevant to the PR

@dataclass
class RelatedFile:
    path: str
    relationship: str  # "imports", "used_by", "test_file", "documentation"
    reason: str  # Why this file is relevant

@dataclass
class RetrievedKnowledge:
    similar_patterns: List[CodePattern]
    best_practices: List[BestPractice]
    related_files: List[RelatedFile]
    architectural_patterns: List[str]  # Relevant architectural guidelines

@dataclass
class Context:
    pr_metadata: PRMetadata
    file_changes: List[FileChange]
    ci_config: CIConfig
    diff_text: str  # raw diff
    ci_status: Optional[str]  # "passing", "failing", None
    retrieved_knowledge: Optional[RetrievedKnowledge] = None  # RAG-retrieved context
```

### 3.2 `models/plan.py`
```python
@dataclass
class ReviewTask:
    type: str  # "correctness", "security", "performance", "style"
    scope: str  # "changed_functions", "all", "high_risk_only"
    priority: str  # "must", "should", "nice"

@dataclass
class ReviewPlan:
    tasks: List[ReviewTask]
    tools: List[str]  # ["eslint", "tsc", "pytest"]
    focus_files: Optional[List[str]]  # if diff is huge
    reason: str  # why this plan was chosen
```

### 3.3 `models/review.py`
```python
@dataclass
class ReviewComment:
    file: str
    line: Optional[int]  # None if it's a general file comment
    diff_hunk: Optional[str]
    category: str  # "must_fix", "should_fix", "nice_to_have"
    issue_type: str  # "bug", "security", "performance", "style"
    description: str
    suggestion: Optional[str]
    confidence: float  # 0.0 - 1.0

@dataclass
class Review:
    must_fix: List[ReviewComment]
    should_fix: List[ReviewComment]
    nice_to_have: List[ReviewComment]
    summary: str
    tool_results_summary: str
```

### 3.4 `models/tool_results.py`
```python
@dataclass
class Issue:
    file: str
    line: int
    column: Optional[int]
    message: str
    severity: str  # "error", "warning"
    rule: Optional[str]  # "eslint-rule-name", etc.

@dataclass
class TestResult:
    test_name: str
    file: str
    passed: bool
    failure_message: Optional[str]
    duration: float

@dataclass
class ToolResults:
    lint_errors: List[Issue]  # from eslint, ruff, etc.
    type_errors: List[Issue]  # from tsc, mypy
    test_results: List[TestResult]
    tool_failures: List[str]  # tools that failed to run
```

---

## 4. LLM Integration

### 4.1 LLM Provider Choice
- **Primary**: OpenAI GPT-4 (or GPT-4o) for planning and review generation
- **Alternative**: Anthropic Claude (for longer context windows)
- **Fallback**: Local LLM (Ollama) for testing without API costs

### 4.2 Prompt Engineering Strategy
- **Planner**: Focused, concise prompts with structured output (JSON)
- **Reviewer**: Context-rich prompts with full diff + tool results
- Use few-shot examples for consistent formatting
- Temperature: 0.2-0.3 (deterministic, focused)

### 4.3 Prompt Templates (`utils/prompt_templates.py`)
- Store all prompts as templates with placeholders
- Easy to iterate on prompts without code changes
- Support different LLM providers (OpenAI vs Anthropic format)

---

## 5. Dependencies & Tech Stack

### Python Packages
```
# Core
fastapi==0.115.0
pydantic>=2.0.0
python-dotenv>=1.0.0

# LLM
openai>=1.0.0  # or anthropic
langchain>=0.1.0  # optional, for structured outputs

# RAG (Retrieval-Augmented Generation)
chromadb>=0.4.0  # vector database for code embeddings
# OR pinecone-client>=3.0.0  # managed vector DB
# OR weaviate-client>=4.0.0  # self-hosted option
tiktoken>=0.5.0  # token counting for embeddings

# GitHub API (minimal, for testing)
pygithub>=2.0.0  # or requests for direct API calls

# Diff parsing
unidiff>=0.7.0  # parse unified diff format

# Tool execution
subprocess  # built-in
pathlib  # built-in

# Utilities
pyyaml>=6.0  # parse CI configs (GitHub Actions, etc.)
```

### External Tools (assumed to be available)
- `eslint` (Node.js)
- `tsc` (TypeScript compiler)
- `ruff` / `mypy` (Python)
- `pytest` (Python tests)
- `semgrep` (optional, security scanning)

### RAG Infrastructure
- **Embedding Model**: OpenAI `text-embedding-3-small` or `text-embedding-ada-002`
- **Vector Database**: Chroma (local, default) or Pinecone/Weaviate (managed/self-hosted)
- **Code Indexing**: Periodic indexing of codebase (on main branch updates or manual trigger)

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Get basic pipeline working end-to-end with mock data

**Tasks**:
1. Set up project structure (create all empty modules)
2. Implement data models (`models/*.py`)
3. Implement `ContextCollector` with mock PR data
4. Implement basic `Planner` (simple LLM call, hardcoded prompt)
5. Implement basic `ToolRunner` (mock tool results for now)
6. Implement basic `Reviewer` (simple LLM call)
7. Create a test script that runs full pipeline with mock data
8. Verify end-to-end flow works

**Success Criteria**: 
- Can run pipeline with mock PR data
- Produces structured review output (JSON)

---

### Phase 2: Context Collection (Week 1-2)
**Goal**: Real context collection from PR diffs

**Tasks**:
1. Implement diff parser (`utils/diff_parser.py`)
   - Parse unified diff format
   - Extract file changes and hunks
   - Map line numbers correctly
2. Implement language detection (from file extensions)
3. Implement CI config inference
   - Parse `package.json` for Node.js projects
   - Parse `requirements.txt` / `pyproject.toml` for Python
   - Parse `.github/workflows/*.yml` for GitHub Actions
4. Integrate with GitHub API (minimal, for testing)
   - Fetch PR diff
   - Fetch PR metadata
5. Test with real PR diff samples
6. **Implement RAG infrastructure** (`utils/codebase_indexer.py`, `services/knowledge_retriever.py`)
   - Set up vector database (Chroma or alternative)
   - Implement codebase indexing (generate embeddings for all source files)
   - Implement retrieval functions (semantic search for similar patterns)
   - Integrate with Context Collector to retrieve knowledge for each PR

**Success Criteria**:
- Can parse real GitHub PR diffs
- Correctly detects languages and tools
- Produces accurate `Context` model
- Successfully indexes codebase and retrieves relevant patterns
- Retrieved knowledge enhances review context with similar code patterns

---

### Phase 3: Tool Execution (Week 2)
**Goal**: Actually run linting/testing tools

**Tasks**:
1. Implement tool execution framework
   - Subprocess execution with timeouts
   - Error handling (tool not found, crashes)
   - Output parsing for each tool
2. Implement parsers for each tool:
   - ESLint JSON output parser
   - TypeScript compiler error parser
   - Ruff output parser
   - Pytest JSON output parser
3. Map tool outputs to file/line in PR diff
4. Test with real repos (clone, checkout PR branch, run tools)

**Success Criteria**:
- Can run eslint/tsc/ruff/pytest on real code
- Correctly parses outputs
- Maps issues to correct file/line numbers

---

### Phase 4: AI Agents (Week 3)
**Goal**: Smart planning and review generation

**Tasks**:
1. Refine planner prompts
   - Add few-shot examples
   - Test with various PR types (small, large, security-focused, etc.)
   - Integrate retrieved knowledge from RAG into planning prompts
2. Implement structured output parsing (JSON schema validation)
3. Refine reviewer prompts
   - Context-aware explanations using retrieved code patterns
   - Better categorization (must/should/nice)
   - Useful code suggestions based on similar patterns found via RAG
   - Consistency checks against codebase patterns
4. Add prompt templates system (`utils/prompt_templates.py`)
5. Test with various real PRs (with and without RAG for comparison)
6. Iterate on prompts based on output quality
7. **Tune RAG retrieval**:
   - Optimize embedding models and similarity thresholds
   - Balance retrieved context size vs. relevance
   - Test different retrieval strategies (semantic vs. pattern-based)

**Success Criteria**:
- Planner generates focused, relevant plans
- Reviewer produces high-quality, actionable comments
- Categories are accurate (must-fix vs nice-to-have)
- RAG successfully retrieves relevant code patterns (similarity > 0.7)
- Reviews reference codebase patterns and suggest consistency improvements
- RAG-enhanced reviews catch more consistency/style issues than baseline

---

### Phase 5: Safety & Polish (Week 3-4)
**Goal**: Add guardrails and refine output

**Tasks**:
1. Implement `SafetyChecker`:
   - Diff size checks
   - High-risk file detection
   - Skip conditions (draft PRs, labels)
2. Refine review formatting:
   - Better markdown formatting
   - Code block syntax highlighting
   - GitHub-specific formatting (file/line links)
3. Add error handling throughout pipeline
4. Add logging/monitoring hooks
5. Create example outputs for documentation

**Success Criteria**:
- No false positives on draft PRs
- Handles large diffs gracefully
- Review output is well-formatted and readable

---

### Phase 6: Testing & Validation (Week 4)
**Goal**: Test with real-world scenarios

**Tasks**:
1. Collect sample PRs from open-source repos
2. Run agent on various PR types:
   - Bug fixes
   - Features
   - Refactoring
   - Security patches
3. Compare agent output with human reviews
4. Tune prompts/parameters based on results
5. Document edge cases and limitations

**Success Criteria**:
- Agent catches real bugs/issues
- False positive rate is low
- Output is comparable to human reviewers

---

## 7. Testing Strategy

### Unit Tests
- Test each component in isolation
- Mock LLM calls (use fixture responses)
- Test edge cases (empty diff, huge diff, tool failures)

### Integration Tests
- Test full pipeline with mock data
- Test with real PR diffs (fixtures)
- Test tool execution (requires actual tools installed)

### Manual Testing
- Run on real open-source PRs
- Compare output to human reviews
- Iterate on prompts

---

## 8. Configuration

### Environment Variables
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...  # optional
GITHUB_TOKEN=...  # for testing GitHub API

# LLM settings
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000

# Embedding model (for RAG)
EMBEDDING_MODEL=text-embedding-3-small
# OR EMBEDDING_MODEL=text-embedding-ada-002

# Vector database settings
VECTOR_DB_TYPE=chroma  # or "pinecone", "weaviate"
CHROMA_PERSIST_DIR=./data/chroma_db
# If using Pinecone:
# PINECONE_API_KEY=...
# PINECONE_ENVIRONMENT=...
# PINECONE_INDEX_NAME=lenssearch-code-index

# RAG retrieval settings
RAG_TOP_K=5  # Number of similar patterns to retrieve
RAG_SIMILARITY_THRESHOLD=0.7  # Minimum similarity score
RAG_ENABLED=true  # Toggle RAG on/off

# Tool paths (if not in PATH)
ESLINT_PATH=/usr/local/bin/eslint
TSC_PATH=/usr/local/bin/tsc

# Safety thresholds
MAX_DIFF_SIZE=1000
MIN_AUTO_FIX_CONFIDENCE=0.8
```

---

## 9. Future Enhancements (Not in Scope Now)

- **Fix Mode**: Auto-generate fixes and create PRs
- **GitHub Integration**: Webhook handler, PR comment posting
- **Frontend**: Dashboard for reviewing agent output
- **CI/CD**: GitHub Actions integration
- **Advanced Tools**: Semgrep custom rules, dependency scanning
- **Learning**: Fine-tune on historical PR reviews
- **Advanced RAG**:
  - Incremental indexing (only re-index changed files)
  - Multi-modal RAG (include diagrams, architecture docs)
  - Cross-repository pattern learning
  - Historical PR review knowledge base (learn from past reviews)

---

## 10. Success Metrics

### Phase 1 Success
- ✅ Pipeline runs end-to-end with mock data
- ✅ Produces structured JSON output

### Phase 2-3 Success
- ✅ Correctly parses real PR diffs
- ✅ Successfully runs tools on real code
- ✅ Maps issues to correct locations

### Phase 4 Success
- ✅ Planner generates relevant plans
- ✅ Reviewer catches real bugs/issues
- ✅ False positive rate < 20%

### Phase 5-6 Success
- ✅ Handles edge cases gracefully
- ✅ Output quality comparable to human reviewers
- ✅ Ready for integration with GitHub

---

## Notes

- Start simple: mock data → real parsing → real tools → real AI → RAG enhancement
- Iterate on prompts frequently (they make the biggest difference)
- Test with real PRs early (not just synthetic data)
- Keep LLM calls focused (don't send entire repo, just relevant diffs + retrieved patterns)
- Cache tool results when possible (don't re-run on every iteration)
- **RAG considerations**:
  - Index codebase once (or periodically), retrieve on-demand
  - Balance retrieval quality vs. context size (top-K patterns only)
  - RAG is optional enhancement - system should work without it for MVP
  - Consider codebase size: may need chunking for large repos
  - Test retrieval relevance before integrating into prompts

