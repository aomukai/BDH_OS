
import os

def run_audit():
    audit_tasks = [
        {
            "file_path": "docs/bdh_cognitive_os_design.md",
            "old_string": "      inference.py
      harness.py
      chat.py",
            "new_string": "      inference.py
      harness.py"
        },
        {
            "file_path": "docs/bdh_cognitive_os_design.md",
            "old_string": "    loras/
        skills/
        dreams/
        index.json",
            "new_string": "    loras/
        skills/
        dreams/"
        },
        {
            "file_path": "AGENTS.md",
            "old_string": "- `core/bdh_100m_final.pt` — trained checkpoint (READ-ONLY)",
            "new_string": "- `core/bdh_150m_current.pt` — trained checkpoint (READ-ONLY)"
        },
        {
            "file_path": "docs/bdh_long_term_vision.md",
            "old_string": "## 6. The role of Hermes and Claude in the present-day path

In April 2026, the current tool ecosystem makes a new design route possible.

Instead of trying to brute-force the final exocortex system directly, the project can proceed through a powerful intermediate architecture:

- Hermes Agent as orchestrator
- Claude as execution model",
            "new_string": "## 6. The role of Hermes and Gemini in the present-day path

In April 2026, the current tool ecosystem makes a new design route possible.

Instead of trying to brute-force the final exocortex system directly, the project can proceed through a powerful intermediate architecture:

- Hermes Agent as orchestrator
- Gemini CLI as executor / worker"
        },
        {
            "file_path": "docs/mommy_says_machine.md",
            "old_string": "| Teacher | Nemotron 3 Super 120B via build.nvidia.com API |",
            "new_string": "| Teacher | Gemini via API |"
        },
        {
            "file_path": "docs/mommy_says_machine.md",
            "old_string": "  teacher.py            ← nemotron API wrapper +",
            "new_string": "  teacher.py            ← Gemini API wrapper +"
        },
        {
            "file_path": "docs/mommy_says_machine.md",
            "old_string": "  model: "nvidia/nemotron-3-super-120b-a12b"",
            "new_string": "  model: "gemini/gemini-pro""
        },
        {
            "file_path": "README.md",
            "old_string": "dream_queue/               queued offline-consolidation items
knowledge/                 external memory / knowledge artifacts",
            "new_string": ""
        }
    ]

    for task in audit_tasks:
        try:
            with open(task["file_path"], "r") as f:
                content = f.read()
            
            new_content = content.replace(task["old_string"], task["new_string"])

            if content != new_content:
                with open(task["file_path"], "w") as f:
                    f.write(new_content)
                print(f"Updated {task['file_path']}")
            else:
                print(f"No changes needed for {task['file_path']}")

        except FileNotFoundError:
            print(f"Could not find file {task['file_path']}")

    # Move dragon_vocab_gap_categories.md
    source_path = "docs/dragon_vocab_gap_categories.md"
    archive_dir = "archive/docs"
    destination_path = os.path.join(archive_dir, os.path.basename(source_path))

    if os.path.exists(source_path):
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        os.rename(source_path, destination_path)
        print(f"Archived {source_path} to {destination_path}")

if __name__ == "__main__":
    run_audit()
