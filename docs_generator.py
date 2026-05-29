#!/usr/bin/env python3
import os
import ast
import re
import time
from typing import Dict, List, Any

# Directories and files to exclude from scanning
EXCLUDE_DIRS = {
    'venv', 'node_modules', '.git', '__pycache__', '.next', 'out', 
    'artifacts', '.gemini', '.github', 'dist', 'build', 'static'
}
EXCLUDE_FILES = {
    'MarketDataFeed_pb2.py', 'docs_generator.py'
}

def extract_python_docs(filepath: str) -> Dict[str, Any]:
    """
    Parses a Python file using the ast module to extract class and function details.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except Exception as e:
        return {'error': f"Failed to parse AST: {str(e)}", 'functions': [], 'classes': []}

    functions = []
    classes = []

    # Extract module docstring
    module_doc = ast.get_docstring(tree) or "No description provided."

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Module-level function
            func_name = node.name
            args = [arg.arg for arg in node.args.args]
            doc = ast.get_docstring(node) or "No description provided."
            is_async = isinstance(node, ast.AsyncFunctionDef)
            functions.append({
                'name': func_name,
                'signature': f"{'async ' if is_async else ''}def {func_name}({', '.join(args)})",
                'docstring': doc
            })
        elif isinstance(node, ast.ClassDef):
            # Class definition
            class_name = node.name
            class_doc = ast.get_docstring(node) or "No description provided."
            methods = []
            
            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    method_name = item.name
                    # Ignore private methods except __init__
                    if method_name.startswith('_') and method_name != '__init__':
                        continue
                    args = [arg.arg for arg in item.args.args]
                    doc = ast.get_docstring(item) or "No description provided."
                    is_async = isinstance(item, ast.AsyncFunctionDef)
                    methods.append({
                        'name': method_name,
                        'signature': f"{'async ' if is_async else ''}def {method_name}({', '.join(args)})",
                        'docstring': doc
                    })
            classes.append({
                'name': class_name,
                'docstring': class_doc,
                'methods': methods
            })

    return {
        'doc': module_doc,
        'functions': functions,
        'classes': classes
    }

def extract_js_ts_docs(filepath: str) -> Dict[str, Any]:
    """
    Parses a JS/TS/TSX file using regex to extract function definitions, React components, 
    and their preceding comment blocks.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    content = "".join(lines)
    
    # Simple heuristics to find JSDoc blocks and the following function declaration
    # Matches: /** ... */ followed by export function, const, etc.
    functions = []
    
    # Regex to catch function definitions:
    # 1. export default function Name(...)
    # 2. export const Name = (...) =>
    # 3. function Name(...)
    # 4. const Name = (...) =>
    func_pattern = re.compile(
        r'(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>)'
    )

    # Let's do a line-by-line check to catch comments easily
    current_comment = []
    in_comment = False
    
    for i, line in enumerate(lines):
        striped = line.strip()
        
        # Check comment block
        if striped.startswith('/**') or striped.startswith('/*'):
            in_comment = True
            current_comment = []
            comment_content = striped.replace('/**', '').replace('/*', '').strip()
            if comment_content:
                current_comment.append(comment_content)
            continue
        elif in_comment and (striped.endswith('*/') or '*/' in striped):
            in_comment = False
            comment_content = striped.replace('*/', '').strip()
            if comment_content:
                current_comment.append(comment_content)
            continue
        elif in_comment:
            comment_content = striped.lstrip('*').strip()
            current_comment.append(comment_content)
            continue
        
        # Look for single line comments immediately before
        if striped.startswith('//'):
            current_comment.append(striped.replace('//', '').strip())
            continue
            
        # Match function declarations
        match = func_pattern.search(line)
        if match:
            func_name = match.group(1) or match.group(2)
            if func_name:
                # Get the full signature
                signature = line.strip().rstrip('{').rstrip(';')
                docstring = "\n".join(current_comment) if current_comment else "No description provided."
                
                # Check if it's a React hook or component
                is_hook = func_name.startswith('use')
                is_component = func_name[0].isupper() if func_name else False
                
                type_label = "Function"
                if is_hook:
                    type_label = "React Hook"
                elif is_component:
                    type_label = "React Component"
                
                functions.append({
                    'name': func_name,
                    'signature': signature,
                    'docstring': docstring,
                    'type': type_label
                })
                current_comment = []
        else:
            # If line is empty or doesn't have a comment, reset comments unless they are immediately preceding
            if not striped:
                current_comment = []

    return {
        'doc': "TypeScript/JavaScript Source Component",
        'functions': functions,
        'classes': []
    }

def scan_project(root_dir: str) -> Dict[str, Dict[str, Any]]:
    """
    Scans the workspace directory and extracts documentation from source files.
    """
    docs_db = {}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        
        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
                
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_dir)
            
            if filename.endswith('.py'):
                docs_db[rel_path] = extract_python_docs(filepath)
            elif filename.endswith(('.ts', '.tsx', '.js', '.jsx')):
                docs_db[rel_path] = extract_js_ts_docs(filepath)
                
    return docs_db

def generate_markdown(docs_db: Dict[str, Dict[str, Any]]) -> str:
    """
    Formulates a structured Markdown document from the extracted documentation DB.
    """
    md = []
    md.append("# Valkyrie Application Architecture & Function Reference")
    md.append("\n*This file is automatically generated and updated in real-time as function signatures, arguments, or docstrings change.*")
    md.append("\n---\n")

    # Table of Contents
    md.append("## Table of Contents")
    for filepath in sorted(docs_db.keys()):
        file_label = filepath.replace(os.sep, "/")
        anchor = file_label.lower().replace('.', '').replace('/', '').replace(' ', '-')
        md.append(f"- [{file_label}](#{anchor})")
    md.append("\n---\n")

    # Details
    for filepath in sorted(docs_db.keys()):
        file_label = filepath.replace(os.sep, "/")
        anchor = file_label.lower().replace('.', '').replace('/', '').replace(' ', '-')
        file_data = docs_db[filepath]
        
        md.append(f"## {file_label}")
        if 'doc' in file_data and file_data['doc']:
            md.append(f"*{file_data['doc']}*")
        md.append("")
        
        if 'error' in file_data:
            md.append(f"> [!WARNING]\n> {file_data['error']}\n")
            continue

        # Classes
        if file_data['classes']:
            md.append("### Classes")
            for cls in file_data['classes']:
                md.append(f"#### class `{cls['name']}`")
                md.append(f"{cls['docstring']}\n")
                if cls['methods']:
                    md.append("##### Methods:")
                    for method in cls['methods']:
                        md.append(f"- **`{method['name']}`**")
                        md.append(f"  *Signature*: `{method['signature']}`")
                        md.append(f"  *Description*: {method['docstring']}\n")
            md.append("")

        # Functions / Components
        if file_data['functions']:
            md.append("### Functions & Endpoints")
            for func in file_data['functions']:
                type_label = func.get('type', 'Function')
                md.append(f"#### `{func['name']}` ({type_label})")
                md.append(f"- **Signature**: `{func['signature']}`")
                md.append(f"- **Description**:\n```text\n{func['docstring']}\n```\n")
            md.append("")
            
        md.append("\n---\n")

    return "\n".join(md)

def run_documentation_generation(root_dir: str, output_path: str):
    """
    Scans code files and updates the documentation markdown file.
    """
    print("Scanning workspace files for function references...")
    docs_db = scan_project(root_dir)
    markdown_content = generate_markdown(docs_db)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"✅ Successfully updated {os.path.basename(output_path)}!")

def get_all_file_mtimes(root_dir: str) -> Dict[str, float]:
    """
    Retrieves modification times for all source files in the project.
    """
    mtimes = {}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
            if filename.endswith(('.py', '.ts', '.tsx', '.js', '.jsx')):
                filepath = os.path.join(dirpath, filename)
                mtimes[filepath] = os.path.getmtime(filepath)
    return mtimes

def watch_project_and_update(root_dir: str, output_path: str):
    """
    Runs in a continuous loop, monitoring file modifications and updating documentation.
    """
    print(f"👀 Watching for source file modifications in {root_dir}...")
    run_documentation_generation(root_dir, output_path)
    
    last_mtimes = get_all_file_mtimes(root_dir)
    
    try:
        while True:
            time.sleep(2)
            current_mtimes = get_all_file_mtimes(root_dir)
            
            # Check for changes
            has_changes = False
            if set(current_mtimes.keys()) != set(last_mtimes.keys()):
                has_changes = True
            else:
                for path, mtime in current_mtimes.items():
                    if last_mtimes.get(path) != mtime:
                        has_changes = True
                        break
            
            if has_changes:
                print("🔄 Change detected in source files. Regenerating documentation...")
                try:
                    run_documentation_generation(root_dir, output_path)
                except Exception as e:
                    print(f"❌ Error updating documentation: {e}")
                last_mtimes = current_mtimes
    except KeyboardInterrupt:
        print("\n👋 Stopped watching.")

if __name__ == "__main__":
    import sys
    workspace = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(workspace, "APP_FUNCTIONS_DOC.md")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        watch_project_and_update(workspace, output)
    else:
        run_documentation_generation(workspace, output)
