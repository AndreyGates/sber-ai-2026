import ast
from pathlib import Path


FORBIDDEN_CALLS = {"exec", "eval", "compile"}
FORBIDDEN_SUBPROCESS = {"subprocess", "os.system", "os.popen"}

PIPELINE_DIR = Path(__file__).resolve().parents[3] / "src" / "code_review"


class _CodeExecutionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Call(self, node):
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            parts = []
            curr = func
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            name = ".".join(reversed(parts))

        if name in FORBIDDEN_CALLS:
            self.violations.append(f"Line {node.lineno}: forbidden call {name}()")
        if name and any(name.startswith(fs) for fs in FORBIDDEN_SUBPROCESS):
            self.violations.append(f"Line {node.lineno}: forbidden call {name}()")

        self.generic_visit(node)


def test_no_code_execution_in_pipeline():
    violations = []
    for py_file in PIPELINE_DIR.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        visitor = _CodeExecutionVisitor()
        visitor.visit(tree)
        for v in visitor.violations:
            violations.append(f"{py_file.name}: {v}")

    assert not violations, f"Code execution violations found:\n" + "\n".join(violations)
