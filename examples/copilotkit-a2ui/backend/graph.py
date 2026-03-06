from typing import TypedDict, List
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool

class AgentState(TypedDict):
    messages: List[BaseMessage]
    search_results: List[str]
    status: str

@tool
def search_products(query: str):
    """Search for products based on a query."""
    return ["Product A", "Product B", "Product C"]

@tool
def show_product(product_id: str):
    """Display a specific product to the user."""
    return f"Displaying product {product_id}"

def call_model(state: AgentState):
    # Simplified logic: just add a mock search result and end
    # In a real app, this would be an LLM call using the tools
    return {
        "messages": [HumanMessage(content="I found some products for you.")],
        "search_results": ["Product A", "Product B"],
        "status": "done"
    }

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)

graph = workflow.compile()
