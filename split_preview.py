import re

with open("web/src/stores/agentV3.ts", "r") as f:
    lines = f.readlines()

boundaries = []
for i, line in enumerate(lines):
    if line.startswith("export interface AgentState"): boundaries.append(("AgentState", i))
    elif line.startswith("export const useAgentStore"): boundaries.append(("useAgentStore", i))
    elif line.startswith("function "): boundaries.append((line.strip(), i))
    elif line.startswith("const "): boundaries.append((line.strip(), i))

for name, line_num in boundaries:
    print(f"{line_num}: {name}")
