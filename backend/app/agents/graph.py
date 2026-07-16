from typing import Any, TypedDict


class TestFlowState(TypedDict, total=False):
    task_id: int
    batch_id: int
    generated_count: int
    completed_count: int
    report_id: int
    errors: list[str]


def build_test_flow() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(TestFlowState)

    def parse_task(state: TestFlowState) -> TestFlowState:
        return {**state, "errors": state.get("errors", [])}

    def summarize(state: TestFlowState) -> TestFlowState:
        return state

    graph.add_node("task_parser", parse_task)
    graph.add_node("reporter", summarize)
    graph.set_entry_point("task_parser")
    graph.add_edge("task_parser", "reporter")
    graph.add_edge("reporter", END)
    return graph.compile()

