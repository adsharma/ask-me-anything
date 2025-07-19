# server.py - A simple MCP server that can add, subtract, multiply, and divide two numbers
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Calculator")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers

    Args:
        a: First number
        b: Second number
    """
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract second number from first number

    Args:
        a: First number
        b: Second number
    """
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers

    Args:
        a: First number
        b: Second number
    """
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide first number by second number

    Args:
        a: First number
        b: Second number
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
