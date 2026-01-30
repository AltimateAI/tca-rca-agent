"""
AST-Based Code Merger
Safely merges fixes into existing code without corrupting files
"""

import ast
import re
from typing import Optional


class CodeMerger:
    """AST-based code merging for Python and TypeScript."""

    @staticmethod
    def merge_python_fix(
        original_content: str, fix_code: str, function_name: str
    ) -> str:
        """
        Replace a Python function using AST transformation.

        Args:
            original_content: Original file content
            fix_code: New function code (complete function)
            function_name: Name of function to replace

        Returns:
            Updated file content with function replaced
        """
        try:
            # Parse both trees
            original_tree = ast.parse(original_content)
            fix_tree = ast.parse(fix_code)

            # Extract the fixed function node
            fixed_function = None
            for node in ast.walk(fix_tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    fixed_function = node
                    break
                elif isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
                    fixed_function = node
                    break

            if not fixed_function:
                raise ValueError(f"Function '{function_name}' not found in fix code")

            # Create transformer to replace the function
            class FunctionReplacer(ast.NodeTransformer):
                def visit_FunctionDef(self, node):
                    if node.name == function_name:
                        return fixed_function
                    return node

                def visit_AsyncFunctionDef(self, node):
                    if node.name == function_name:
                        return fixed_function
                    return node

            # Apply transformation
            transformer = FunctionReplacer()
            new_tree = transformer.visit(original_tree)

            # Convert back to code
            return ast.unparse(new_tree)

        except SyntaxError as e:
            raise SyntaxError(f"Failed to parse code: {e}")

    @staticmethod
    def merge_typescript_fix(
        original_content: str, fix_code: str, function_name: str
    ) -> str:
        """
        Replace a TypeScript function using regex pattern matching.

        Note: Full AST parsing for TypeScript would require ts-morph.
        This uses a simpler regex approach for common cases.

        Args:
            original_content: Original file content
            fix_code: New function code (complete function)
            function_name: Name of function to replace

        Returns:
            Updated file content with function replaced
        """
        # Pattern to match function declaration (various styles)
        patterns = [
            # function name(...) { ... }
            rf"(function\s+{re.escape(function_name)}\s*\([^)]*\)[^{{]*\{{(?:[^{{}}]*|\{{[^{{}}]*\}})*\}})",
            # const name = (...) => { ... }
            rf"(const\s+{re.escape(function_name)}\s*=\s*\([^)]*\)\s*=>\s*\{{(?:[^{{}}]*|\{{[^{{}}]*\}})*\}})",
            # async function name(...) { ... }
            rf"(async\s+function\s+{re.escape(function_name)}\s*\([^)]*\)[^{{]*\{{(?:[^{{}}]*|\{{[^{{}}]*\}})*\}})",
        ]

        for pattern in patterns:
            if re.search(pattern, original_content, re.DOTALL):
                # Replace the matched function
                return re.sub(
                    pattern, fix_code.strip(), original_content, count=1, flags=re.DOTALL
                )

        # If no pattern matched, raise error
        raise ValueError(
            f"Function '{function_name}' not found in original TypeScript code"
        )

    @staticmethod
    def merge_generic(
        original_content: str,
        fix_code: str,
        file_path: str,
        function_name: Optional[str] = None,
    ) -> str:
        """
        Merge fix based on file type.

        Args:
            original_content: Original file content
            fix_code: New code to merge
            file_path: Path to file (used to determine language)
            function_name: Name of function to replace (if known)

        Returns:
            Updated file content
        """
        if file_path.endswith(".py"):
            if function_name:
                return CodeMerger.merge_python_fix(
                    original_content, fix_code, function_name
                )
            else:
                # If no function name, just append (for new code)
                return original_content + "\n\n" + fix_code

        elif file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            if function_name:
                return CodeMerger.merge_typescript_fix(
                    original_content, fix_code, function_name
                )
            else:
                return original_content + "\n\n" + fix_code

        else:
            # For other file types, simple append
            return original_content + "\n\n" + fix_code


# Example usage and test
if __name__ == "__main__":
    # Test Python merging
    original = '''
def greet(name):
    print(f"Hello {name}")
    return name

def other():
    pass
'''

    fix = '''
def greet(name: str) -> str:
    if not name:
        raise ValueError("Name required")
    print(f"Hello {name}")
    return name
'''

    result = CodeMerger.merge_python_fix(original, fix, "greet")
    print("✅ Python merge test:")
    print(result)
    assert "def greet(name: str) -> str:" in result
    assert "def other():" in result
    assert "raise ValueError" in result
    print("✅ All assertions passed")
