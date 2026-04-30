import os
import json
import re

def get_all_phase_files(phases_dir):
    all_files = []
    # Sort phases numerically
    phases = [d for d in os.listdir(phases_dir) if os.path.isdir(os.path.join(phases_dir, d)) and d.startswith("phase_")]
    phases.sort(key=lambda x: int(x.split('_')[1]))
    
    for phase in phases:
        phase_path = os.path.join(phases_dir, phase)
        # Sort files within phase
        files = [f for f in os.listdir(phase_path) if f.endswith(".md") and re.match(r"phase_\d+.*\.md", f)]
        files.sort()
        for file in files:
            # Exclude non-curriculum files
            if "eval_report" in file or "README" in file or "manifest" in file or "spec" in file:
                continue
            all_files.append(file)
    return all_files

def update_training_sequence(sequence_path, new_files):
    # Read current lines to get the last number
    with open(sequence_path, "r") as f:
        lines = [line for line in f if line.strip()]
        if lines:
            try:
                line_num = int(lines[-1].split()[0])
            except (ValueError, IndexError):
                line_num = len(lines)
        else:
            line_num = 0
    
    with open(sequence_path, "a") as f:
        for file in new_files:
            line_num += 1
            # Simple placeholder for concept, replace with real logic if needed
            concept = file.replace(".md", "").replace("_", " ")
            f.write(f"{line_num:<4} {file}  ({concept})\n")

def create_dependency_graph(sequence_path, phases_dir):
    with open(sequence_path, "r") as f:
        lines = f.readlines()

    files_in_order = [line.split()[1] for line in lines if line.strip()]
    
    graph = {"files": {}}
    
    for i, file_name in enumerate(files_in_order):
        if not file_name.startswith("phase_"):
            continue
        parts = file_name.split('_')
        if len(parts) < 3:
            continue
        phase_num_str = parts[1]
        try:
            phase_num = int(phase_num_str)
        except ValueError:
            print(f"Warning: Could not parse phase number from filename: {file_name}")
            continue
        
        file_path = os.path.join(phases_dir, f"phase_{phase_num}", file_name)
        
        concept = "unknown"
        definition = ""
        
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read()
                # A simple way to get a concept from the first user prompt
                match = re.search(r"\[user\]what is(?: a| an)? (.*)\?", content)
                if match:
                    concept = match.group(1).strip()
                else:
                    # Fallback for different prompt formats
                    match = re.search(r"\[user\](.*)\?", content)
                    if match:
                        concept = match.group(1).strip()
                
                # A simple way to get a definition
                definition_match = re.search(r"\[Ninereeds\](.*?)\n", content)
                if definition_match:
                    definition = definition_match.group(1).strip()


        depends_on = []
        if i > 0:
            depends_on.append(files_in_order[i-1])
            
        graph["files"][file_name] = {
            "concept": concept,
            "phase": phase_num,
            "definition": definition,
            "depends_on": depends_on
        }
        
    return graph

def main():
    phases_dir = "training_data/phases"
    sequence_path = os.path.join(phases_dir, "training_sequence.txt")
    graph_path = os.path.join(phases_dir, "dependency_graph.json")

    # Update training_sequence.txt
    all_files = get_all_phase_files(phases_dir)
    
    with open(sequence_path, "r") as f:
        existing_files = {line.split()[1] for line in f if line.strip()}
        
    new_files = [f for f in all_files if f not in existing_files]

    if new_files:
        print(f"Found {len(new_files)} new files to add to the training sequence.")
        update_training_sequence(sequence_path, new_files)
        print("Updated training_sequence.txt")
    else:
        print("No new files to add to the training sequence.")

    # Re-create dependency_graph.json
    print("Generating new dependency graph...")
    new_graph = create_dependency_graph(sequence_path, phases_dir)

    with open(graph_path, "w") as f:
        json.dump(new_graph, f, indent=2)
    
    print("Updated dependency_graph.json")

if __name__ == "__main__":
    main()
