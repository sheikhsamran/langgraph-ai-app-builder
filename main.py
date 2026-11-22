import sys
sys.path.append("agent")
import os
import streamlit as st
from agent.graph import agent
from agent.tools import PROJECTS_DIR

st.title("Coder Buddy")

# Keep track of whether the agent is running
if "running" not in st.session_state:
    st.session_state.running = False

user_prompt = st.text_area(
    "What do you want to build?",
    disabled=st.session_state.running,
)

if st.button("Generate", disabled=st.session_state.running):
    if user_prompt.strip():
        st.session_state.running = True
        st.session_state.prompt = user_prompt
        st.rerun()

if st.session_state.running:
    coder_count = 0
    with st.spinner("Working..."):
        for step in agent.stream(
            {"user_prompt": st.session_state.prompt},
            {"recursion_limit": 100},
        ):
            node_name = list(step.keys())[0]
            node_output = step[node_name]

            if node_name == "coder":
                coder_count += 1
                title = f"Coder step {coder_count}"
            else:
                title = node_name.capitalize()

            st.write(f"Finished: {title}")
            with st.expander(title, expanded=False):
                st.code(node_output.get("log", "Done"))

    st.session_state.running = False
    st.success("Done!")

# Sidebar: list of generated projects
st.sidebar.title("Projects")

if PROJECTS_DIR.exists():
    for project in sorted(os.listdir(PROJECTS_DIR)):
        project_path = PROJECTS_DIR / project
        if project_path.is_dir():
            with st.sidebar.expander(project):
                for file in sorted(os.listdir(project_path)):
                    file_path = project_path / file
                    if file_path.is_file():
                        if st.button(file, key=f"{project}-{file}"):
                            st.sidebar.code(file_path.read_text())