# server.py - A simple MCP server that can add, subtract, multiply, and divide two numbers
from mcp.server.fastmcp import FastMCP
import duckdb

# Create an MCP server
mcp = FastMCP("Triples")

@mcp.tool()
def print_node_triples(label_to_find):
    """
    Prints knowledge graph triples for a given node label.

    Args:
        label_to_find: The label of the node to find the triples for.

    Returns:
        A string containing the triples for the given node label.
    """
    # Connect to DuckDB and attach the databases
    con = duckdb.connect('knowledge-graph/truthy.db')
    con.execute("ATTACH 'knowledge-graph/labels.db' AS nodes")
    con.execute("ATTACH 'knowledge-graph/edge_meta.db' AS edges")

    # Query to find the node by label and join with relations and edge_types
    query = """
    SELECT 
        l1.e1 AS id,
        l1.label AS subject,
        et.label AS predicate,
        l2.label AS object
    FROM nodes.labels l1
    JOIN relations r ON l1.e1 = r.e1
    JOIN edges.edge_types et ON r.type = et.id
    JOIN nodes.labels l2 ON r.e2 = l2.e1
    WHERE l1.label = ?
    ORDER BY l1.e1
    """
    
    results = "Triples for node '{label_to_find}':\n"
    # Execute the query with the provided label
    df = con.execute(query, [label_to_find]).df()
    if not df.empty:
        for index, row in df.iterrows():
            results += f"id: {row['id']}: ({row['subject']}) - [{row['predicate']}] - ({row['object']})\n"
    else:
        results += f"No triples found for node '{label_to_find}'"    
    
    # Close the connection  
    con.close()
    return results

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
