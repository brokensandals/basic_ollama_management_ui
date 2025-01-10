from nicegui import ui
from datetime import datetime
import argparse
from ollama import Client

class OllamaManagementUI:
    def __init__(self, ollama_url: str):
        self.ollama_url = ollama_url
        self.refreshed_label = ui.label("Initializing...")
        ui.timer(60.0, self.refresh)
        self.ollama = Client(host=ollama_url)

        installed_models_columns = [
            {"name": "name", "label": "Name", "field": "name", "sortable": True, "required": True, "align": "left"},
            {"name": "size", "label": "Size", "field": "size", "sortable": True},
            {"name": "modified_at", "label": "Modified", "field": "modified_at", "sortable": True},
            {"name": "digest", "label": "Digest", "field": "digest"},
            {"name": "format", "label": "Format", "field": "format"},
            {"name": "family", "label": "Family", "field": "family"},
            {"name": "families", "label": "Families", "field": "families"},
            {"name": "parameter_size", "label": "Parameters", "field": "parameter_size", "sortable": True},
            {"name": "quantization_level", "label": "Quantization", "field": "quantization_level"}
        ]
        self.installed_models = {}
        self.installed_models_table = ui.table(title="Installed Models", columns=installed_models_columns, rows=[], row_key="name")
    
    def refresh(self):
        new_model_names = set()
        changed_model_names = set()
        removed_model_names = set(self.installed_models.keys())
        for model in self.ollama.list().models:
            row_dict = {
                "name": model.model,
                "size": model.size,
                "modified_at": model.modified_at,
                "digest": model.digest,
                "format": model.details.format,
                "family": model.details.family,
                "families": ", ".join(model.details.families), # fun fact: if you don't stringify this, the UI will be incredibly slow
                "parameter_size": model.details.parameter_size,
                "quantization_level": model.details.quantization_level
            }
            if model.model in self.installed_models:
                changed_model_names.add(model.model)
            else:
                new_model_names.add(model.model)
            removed_model_names.discard(model.model)
            self.installed_models[model.model] = row_dict
        if removed_model_names:
            to_remove = [self.installed_models[k] for k in removed_model_names]
            self.installed_models_table.remove_rows(to_remove)
            for row in to_remove:
                self.installed_models.pop(row["name"])
        if new_model_names:
            to_add = [self.installed_models[k] for k in new_model_names]
            self.installed_models_table.add_rows(to_add)
        if changed_model_names:
            to_update = [self.installed_models[k] for k in changed_model_names]
            self.installed_models_table.update_rows(to_update)
        
        self.refreshed_label.set_text(f"Last refreshed at {datetime.now().strftime("%H:%M")}")

    def run(self):
        ui.run()


parser = argparse.ArgumentParser()
parser.add_argument("ollama", help="Ollama URL")
args = parser.parse_args()
OllamaManagementUI(args.ollama).run()
