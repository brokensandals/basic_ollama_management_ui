from nicegui import ui
from datetime import datetime
import argparse
from ollama import Client

class OllamaManagementUI:
    def __init__(self, ollama_url: str):
        self.ollama_url = ollama_url
        ui.label(f"Ollama URL: {ollama_url}")
        with ui.row(align_items="baseline"):
            ui.button("Refresh", on_click=self.refresh)
            self.refreshed_label = ui.label("Initializing...")
        ui.timer(60.0, self.refresh)
        self.ollama = Client(host=ollama_url)

        installed_models_columns = [
            {"name": "actions", "label": "Actions", "field": "actions", "align": "left"},
            {"name": "model", "label": "Model", "field": "model", "sortable": True, "required": True, "align": "left"},
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
        # based on https://github.com/zauberzeug/nicegui/discussions/2136
        self.installed_models_table.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn icon="delete" @click="$parent.$emit('delete', props.row.model)" />
            </q-td>
        """)
        self.installed_models_table.on("delete", self.confirm_delete_model)
        ps_columns = [
            {"name": "model", "label": "Model", "field": "model", "sortable": True, "required": True, "align": "left"},
            {"name": "name", "label": "Name", "field": "name", "sortable": True, "required": True, "align": "left"},
            {"name": "expires_at", "label": "Expires", "field": "expires_at", "sortable": True},
            {"name": "size", "label": "Size", "field": "size", "sortable": True},
            {"name": "size_vram", "label": "VRAM", "field": "size_vram", "sortable": True},
            {"name": "digest", "label": "Digest", "field": "digest"},
        ]
        self.ps_models = {}
        self.ps_table = ui.table(title="Running Models", columns=ps_columns, rows=[], row_key="name")
        ui.page_title("Ollama Management")
    
    def refresh_models_list(self):
        try:
            self.installed_models_table.classes(remove="text-negative")
            new_model_names = set()
            changed_model_names = set()
            removed_model_names = set(self.installed_models.keys())
            for model in self.ollama.list().models:
                row_dict = {
                    "model": model.model,
                    "size": f"{model.size:,}",
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
                    self.installed_models.pop(row["model"])
            if new_model_names:
                to_add = [self.installed_models[k] for k in new_model_names]
                self.installed_models_table.add_rows(to_add)
            if changed_model_names:
                to_update = [self.installed_models[k] for k in changed_model_names]
                self.installed_models_table.update_rows(to_update)
            return True
        except Exception as e:
            self.installed_models_table.clear()
            self.installed_models.clear()
            self.installed_models_table.classes(replace="text-negative")
            return False
    
    def refresh_ps(self):
        try:
            self.ps_table.classes(remove="text-negative")
            new_model_names = set()
            changed_model_names = set()
            removed_model_names = set(self.ps_models.keys())
            for model in self.ollama.ps().models:
                row_dict = {
                    "model": model.model,
                    "name": model.name,
                    "expires_at": f"{model.expires_at} ({(model.expires_at - datetime.now(model.expires_at.tzinfo)).total_seconds() / 60:.0f} minutes)" if model.expires_at else None,
                    "size": f"{model.size:,}",
                    "size_vram": f"{model.size_vram:,}",
                    "digest": model.digest
                }
                if model.model in self.ps_models:
                    changed_model_names.add(model.model)
                else:
                    new_model_names.add(model.model)
                removed_model_names.discard(model.model)
                self.ps_models[model.model] = row_dict
            if removed_model_names:
                to_remove = [self.ps_models[k] for k in removed_model_names]
                self.ps_table.remove_rows(to_remove)
                for row in to_remove:
                    self.ps_models.pop(row["model"])
            if new_model_names:
                to_add = [self.ps_models[k] for k in new_model_names]
                self.ps_table.add_rows(to_add)
            if changed_model_names:
                to_update = [self.ps_models[k] for k in changed_model_names]
                self.ps_table.update_rows(to_update)
            return True
        except Exception as e:
            self.ps_table.clear()
            self.ps_models.clear()
            self.ps_table.classes(replace="text-negative")
            return False

    def refresh(self):
        ok = True
        ok = self.refresh_models_list() and ok
        ok = self.refresh_ps() and ok
        if ok:
            self.refreshed_label.set_text(f"Refreshed successfully at {datetime.now().strftime("%H:%M:%S")}")
            self.refreshed_label.classes(replace="text-positive")
        else:
            self.refreshed_label.set_text(f"Failed refresh at {datetime.now().strftime("%H:%M:%S")}")
            self.refreshed_label.classes(replace="text-negative")

    def run(self):
        ui.run()

    def confirm_delete_model(self, evt):
        model_name = evt.args
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Are you sure you want to delete model {model_name}?")
            def delete_and_close():
                self.delete_model(model_name)
                dialog.close()
            with ui.row():
                ui.button("Delete", on_click=delete_and_close, color="red")
                ui.button("Cancel", on_click=dialog.close)
        dialog.open()

    def delete_model(self, model_name: str):
        try:
            self.ollama.delete(model=model_name)
            ui.notify(f"Deleted model {model_name}", type="positive")
        except Exception as e:
            print(f"Failed to delete model {model_name}: {e}")
            ui.notify(f"Failed to delete model {model_name}", type="negative")
            return
        self.installed_models_table.remove_rows([self.installed_models[model_name]])
        self.installed_models.pop(model_name)


parser = argparse.ArgumentParser()
parser.add_argument("ollama", help="Ollama URL")
args = parser.parse_args()
OllamaManagementUI(args.ollama).run()
