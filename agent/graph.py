import os
from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, END
from langchain.agents import create_agent
from agent.prompts import *
from agent.states import *
from agent.tools import *

llm = init_chat_model(
    "openai/gpt-oss-120b",
    model_provider="openai",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def planner_agent(state: dict) -> dict:
    user_prompt = state["user_prompt"]
    response = llm.with_structured_output(Plan).invoke(planner_prompt(user_prompt))

    if response is None:
        raise ValueError("Planner did not return a valid response.")

    set_project_name(response.name)
    return {"plan": response, "log": response.model_dump_json(indent=2)}

def architect_agent(state: dict) -> dict:
    plan = state["plan"]

    response = llm.with_structured_output(TaskPlan).invoke(
        architect_prompt(plan=plan.model_dump_json())
    )

    if response is None:
        raise ValueError("Architect did not return a valid response.")

    response.plan = plan

    return {"task_plan": response, "log": response.model_dump_json(indent=2)}

def coder_agent(state: dict) -> dict:
    coder_state = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps

    if coder_state.current_step_idx >= len(steps):
        return {"coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]

    existing_content = read_file.run(current_task.filepath)
    user_prompt = (
        f"Task: {current_task.task_description}\n"
        f"file: {current_task.filepath}\n"
        f"Existing content: {existing_content}\n"
        "Use write_file(path, content) to save your changes."
    )

    system_prompt = coder_system_prompt()


    coder_tools = [read_file, write_file, list_files, get_current_directory]

    coder_agent = create_agent(
        model=llm,
        tools=coder_tools,
        system_prompt=system_prompt,
    )

    response = coder_agent.invoke(
        {"messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]}
    )

    coder_state.current_step_idx += 1

    return {
        "coder_state": coder_state,
        "log": f"File: {current_task.filepath}\nTask: {current_task.task_description}",
    }

graph = StateGraph(dict)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")
graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"}
)

graph.set_entry_point("planner")

agent = graph.compile()

# png = agent.get_graph().draw_mermaid_png()
# with open("graph.png", "wb") as f:
#     f.write(png)
#
# print(agent.get_graph().draw_mermaid())