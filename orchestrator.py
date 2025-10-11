"""LangGraph-style orchestrator coordinating agents."""
from __future__ import annotations

from typing import Dict

from langgraph.graph import END, StateGraph

from agents.analysis_agent import AnalysisAgent
from agents.chat_agent import ChatAgent
from agents.code_parser_agent import CodeParserAgent
from agents.diagram_agent import DiagramAgent
from agents.embedding_agent import EmbeddingAgent
from agents.graph_agent import GraphAgent
from stores.neo4j_store import Neo4jGraphStore, Neo4jVectorStore


class AnalysisState(dict):
    """State passed between LangGraph nodes."""


def _analysis_workflow() -> StateGraph:
    graph = StateGraph(AnalysisState)

    code_parser = CodeParserAgent()
    analysis_agent = AnalysisAgent()
    embedding_agent = EmbeddingAgent()
    graph_agent = GraphAgent()
    diagram_agent = DiagramAgent()

    def parse_repo(state: AnalysisState) -> AnalysisState:
        return code_parser.run(state)

    def analyze_repo(state: AnalysisState) -> AnalysisState:
        return analysis_agent.run(state)

    def embed_repo(state: AnalysisState) -> AnalysisState:
        state.setdefault("vector_store", Neo4jVectorStore())
        return embedding_agent.run(state)

    def build_graph(state: AnalysisState) -> AnalysisState:
        state.setdefault("graph_store", Neo4jGraphStore())
        return graph_agent.run(state)

    def generate_diagrams(state: AnalysisState) -> AnalysisState:
        return diagram_agent.run(state)

    graph.add_node("parse_repo", parse_repo)
    graph.add_node("analyze_repo", analyze_repo)
    graph.add_node("embed_repo", embed_repo)
    graph.add_node("build_graph", build_graph)
    graph.add_node("generate_diagrams", generate_diagrams)

    graph.set_entry_point("parse_repo")
    graph.add_edge("parse_repo", "analyze_repo")
    graph.add_edge("analyze_repo", "embed_repo")
    graph.add_edge("embed_repo", "build_graph")
    graph.add_edge("build_graph", "generate_diagrams")
    graph.add_edge("generate_diagrams", END)

    return graph


def build_analysis_executor():
    graph = _analysis_workflow()
    return graph.compile()


def run_analysis(repo_url: str) -> Dict[str, object]:
    executor = build_analysis_executor()
    initial_state = AnalysisState(repo_url=repo_url, repo_input=repo_url)
    result = executor.invoke(initial_state)
    diagrams = result.get("diagrams", {})
    return {
        "analysis": result.get("analysis", ""),
        "knowledge_graph": result.get("knowledge_graph", {}),
        "hld": diagrams.get("hld"),
        "lld": diagrams.get("lld"),
    }


def run_chat(question: str) -> Dict[str, object]:
    chat_agent = ChatAgent()
    state = AnalysisState(chat_question=question, vector_store=Neo4jVectorStore())
    result = chat_agent.run(state)
    return {
        "answer": result.get("chat_answer", "No answer available"),
        "context": result.get("chat_context", ""),
    }
