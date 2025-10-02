"""Extended string formatter with eval-based expressions."""

from __future__ import annotations

import ast
import re
from functools import partial
from logging import Logger, getLogger


# find every occurrence of token within string with multiple tokens
token_regex_pattern = re.compile(r"\{[^{}]+\}")

# detect expression tokens with single curly braces but exclude tokens
# with double curly braces
expression_token_regex_pattern = re.compile(
    r"\{(?![a-zA-Z_][a-zA-Z0-9_]*:[0-9a-zA-Z#+\- .]+\})[^{}]*[\.\[][^{}]*\}(?!\})"
)

# Whitelist of allowed operations in expressions
ALLOWED_ATTRIBUTES = [
    "split",
    "join",
    "upper",
    "capitalize",
    "lower",
    "strip",
    "lstrip",
    "rstrip",
    "replace",
    "startswith",
    "endswith",
    "format",
    "count",
]

# Whitelist of allowed builtins
ALLOWED_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    "bool": bool,
    "max": max,
    "min": min,
    "sum": sum,
    "round": round,
    "abs": abs,
    "enumerate": enumerate,
    "zip": zip,
    "range": range,
}


def validate_expression(expr: str) -> bool:
    """Validate that an expression only uses whitelisted operations.

    Args:
        expr (str): The expression to validate.

    Returns:
        bool: True if the expression is valid, False otherwise.
    """
    try:
        # Parse the expression into an abstract syntax tree
        tree = ast.parse(expr, mode="eval")

        # Walk through the AST to check for disallowed operations
        for node in ast.walk(tree):
            # Check for attribute access
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name not in ALLOWED_ATTRIBUTES:
                    return False

            # Check for function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name not in ALLOWED_BUILTINS:
                        return False
                elif isinstance(node.func, ast.Attribute):
                    # Already checked attributes above
                    pass
                else:
                    # Disallow other complex function calls
                    return False

            # Disallow imports, comprehensions, and other complex expressions
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ListComp,
                    ast.DictComp,
                    ast.SetComp,
                    ast.GeneratorExp,
                    ast.Lambda,
                ),
            ):
                return False

        return True
    except SyntaxError:
        return False


def eval_expression_safely(
    expr: str, context: dict[str, str | int | float]
) -> str:
    """Safely evaluate an expression with restricted context.

    Args:
        expr (str): The expression to evaluate.
        context (dict[str, str | int | float]): The context variables.

    Returns:
        str: The result of the evaluation.

    Raises:
        ValueError: If the expression contains disallowed operations.
    """
    if not validate_expression(expr):
        raise ValueError(f"Expression contains disallowed operations: {expr}")

    # Create a safe evaluation environment with only allowed functions
    safe_globals = ALLOWED_BUILTINS.copy()

    # Convert the result to string for consistency
    result = eval(expr, safe_globals, context)
    return str(result)


def format_expression_string(
    template_string: str, context: dict[str, str | int | float]
) -> str:
    """Format a template string with expressions using eval.

    Args:
        template_string (str): The template string to format.
        context (dict): The context to use for formatting.

    Returns:
        str: The formatted string.
    """

    def replace_expression(match):
        expr = match.group(0)[
            2:-2
        ].strip()  # Remove {{ }} and strip whitespace
        return eval_expression_safely(expr, context)

    # Replace expressions in {{ expr }} format
    pattern = r"\{\{\s*([^{}]+)\s*\}\}"
    return re.sub(pattern, replace_expression, template_string)


def extended_format(
    template_string: str, context: dict[str, str | int | float],
    logger: Logger | None = None,
) -> str:
    """Format a template string using both str.format and expression evaluation.

    This function first tries to format the string using str.format. If there
    are any remaining tokens with expressions, it will evaluate them.

    Args:
        template_string (str): The template string to format.
        context (dict): The context to use for formatting.
        logger (Logger | None): The logger to use for logging errors.

    Returns:
        str: The formatted string.
    """
    log = logger or getLogger(__name__)
    output_string = template_string

    # Format any string which is formattable with str.format
    tokens = token_regex_pattern.findall(output_string)
    for token in tokens:
        if not token:
            continue
        try:
            token_formatted = token.format(**context)
            output_string = output_string.replace(token, token_formatted)
        except (KeyError, AttributeError):
            # Skip tokens that cannot be formatted with the current context
            pass

    # First convert all expression tokens to double curly braces format
    expression_tokens = expression_token_regex_pattern.findall(output_string)
    if expression_tokens:
        for token in expression_tokens:
            if not token:
                continue
            # Convert to expression format
            expr_token = "{{ " + token[1:-1] + " }}"
            output_string = output_string.replace(token, expr_token)
    log.debug(
        f"Formatted string before expression evaluation: {output_string}")
    # Evaluate expressions in the format {{ expr }}
    return format_expression_string(output_string, context)

__all__ = ["extended_format"]
