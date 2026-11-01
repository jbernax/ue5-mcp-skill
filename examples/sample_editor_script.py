"""
Sample in-Editor Python script executed via Unreal Engine MCP.
Can be executed via CLI:
  python scripts/mcp_cli.py exec-python --file examples/sample_editor_script.py
"""
import unreal

def inspect_editor_state():
    unreal.log("=== UE5 MCP In-Editor Python Inspection ===")
    
    # Active world and level
    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.log(f"Active Editor World: {world.get_name() if world else 'None'}")
    
    # Selected actors count
    selected = unreal.EditorLevelLibrary.get_selected_level_actors()
    unreal.log(f"Selected Actors: {len(selected)}")
    
    # All actors in level
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    unreal.log(f"Total Actors in Level: {len(all_actors)}")
    
    return {
        "world": world.get_name() if world else None,
        "selected_actors_count": len(selected),
        "total_actors_count": len(all_actors),
    }

if __name__ == "__main__":
    inspect_editor_state()
