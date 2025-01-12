from nicegui import ui
from datetime import datetime
import argparse
from ollama import AsyncClient
import logging

logger = logging.getLogger(__name__)

class OllamaManagementUI:
    def __init__(self, ollama_url: str, refresh_interval: int = 60):
        self.ollama_url = ollama_url
        ui.label(f"Ollama URL: {ollama_url}")
        with ui.row(align_items="baseline"):
            ui.button("Refresh", on_click=self.refresh)
            self.refreshed_label = ui.label("Initializing...")
        ui.timer(refresh_interval, self.refresh)
        self.ollama = AsyncClient(host=ollama_url)

        self.creation_card = ui.card()
        with self.creation_card:
            with ui.row(align_items="baseline"):
                self.new_model_input = ui.input(label="Pull or Create Model", placeholder="Enter model name")
                ui.button("Pull", on_click=self.pull_model)
                ui.button("Create Using Modelfile", on_click=self.create_using_modelfile)

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
        self.installed_models_table = ui.table(title="Installed Models", columns=installed_models_columns, rows=[], row_key="model")
        # based on https://github.com/zauberzeug/nicegui/discussions/2136
        self.installed_models_table.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn icon="info" @click="$parent.$emit('info', props.row.model)" />
                <q-btn icon="delete" @click="$parent.$emit('delete', props.row.model)" />
            </q-td>
        """)
        self.installed_models_table.on("info", self.show_model_info)
        self.installed_models_table.on("delete", self.confirm_delete_model)

        ps_columns = [
            {"name": "model", "label": "Model", "field": "model", "sortable": True, "required": True, "align": "left"},
            {"name": "name", "label": "Name", "field": "name", "sortable": True, "required": True, "align": "left"},
            {"name": "expires_at", "label": "Expires", "field": "expires_at", "sortable": True},
            {"name": "size", "label": "Size", "field": "size", "sortable": True},
            {"name": "size_vram", "label": "VRAM", "field": "size_vram", "sortable": True},
            {"name": "digest", "label": "Digest", "field": "digest"},
        ]
        self.ps_table = ui.table(title="Running Models", columns=ps_columns, rows=[], row_key="name")
        ui.page_title("Ollama Management")
    
    async def refresh_models_list(self):
        try:
            self.installed_models_table.classes(remove="text-negative")
            rows = []
            for model in (await self.ollama.list()).models:
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
                rows.append(row_dict)
            self.installed_models_table.rows[:] = rows
            self.installed_models_table.update()
            return True
        except Exception as e:
            logger.exception("Failed to refresh models list")
            self.installed_models_table.clear()
            self.installed_models_table.classes(replace="text-negative")
            return False
    
    async def refresh_ps(self):
        try:
            self.ps_table.classes(remove="text-negative")
            rows = []
            for model in (await self.ollama.ps()).models:
                row_dict = {
                    "model": model.model,
                    "name": model.name,
                    "expires_at": f"{model.expires_at} ({(model.expires_at - datetime.now(model.expires_at.tzinfo)).total_seconds() / 60:.0f} minutes)" if model.expires_at else None,
                    "size": f"{model.size:,}",
                    "size_vram": f"{model.size_vram:,}",
                    "digest": model.digest
                }
                rows.append(row_dict)
            self.ps_table.rows[:] = rows
            self.ps_table.update()
            return True
        except Exception as e:
            logger.exception("Failed to refresh running models")
            self.ps_table.clear()
            self.ps_table.classes(replace="text-negative")
            return False

    async def refresh(self):
        ok = True
        ok = await self.refresh_models_list() and ok
        ok = await self.refresh_ps() and ok
        if ok:
            self.refreshed_label.set_text(f"Refreshed successfully at {datetime.now().strftime("%H:%M:%S")}")
            self.refreshed_label.classes(replace="text-positive")
        else:
            self.refreshed_label.set_text(f"Failed refresh at {datetime.now().strftime("%H:%M:%S")}")
            self.refreshed_label.classes(replace="text-negative")

    def run(self):
        ui.run()

    async def confirm_delete_model(self, evt):
        model_name = evt.args
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Are you sure you want to delete model {model_name}?")
            async def delete_and_close():
                await self.delete_model(model_name)
                dialog.close()
            with ui.row():
                ui.button("Delete", on_click=delete_and_close, color="red")
                ui.button("Cancel", on_click=dialog.close)
        dialog.open()

    async def delete_model(self, model_name: str):
        try:
            await self.ollama.delete(model=model_name)
            ui.notify(f"Deleted model {model_name}", type="positive")
        except Exception as e:
            print(f"Failed to delete model {model_name}: {e}")
            ui.notify(f"Failed to delete model {model_name}", type="negative")
            return
        await self.refresh_models_list()

    async def pull_model(self):
        model_name = self.new_model_input.value
        if not model_name:
            ui.notify("Please enter a model name", type="warning")
            return
        status_row = None
        status_label = None
        progress_bar = None
        with self.creation_card:
            status_row = ui.row()
        with status_row:
            ui.label(f"Pulling {model_name}...")
            status_label = ui.label()
            progress_bar = ui.linear_progress()
        try:
            async for progress in await self.ollama.pull(model=model_name, stream=True):
                status_label.set_text(progress.status)
                progress_bar.set_value(progress.completed / progress.total if progress.completed else 0)
            ui.notify(f"Successfully pulled model {model_name}", type="positive")
        except Exception as e:
            ui.notify(f"Failed to pull model {model_name}: {str(e)}", type="negative")
        status_row.delete()
        await self.refresh_models_list()

    async def create_using_modelfile(self):
        model_name = self.new_model_input.value
        if not model_name:
            ui.notify("Please enter a model name", type="warning")
            return
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Create a new model based on {model_name}?")
            modelfile = ui.textarea("Modelfile", placeholder="FROM llama3.3:70b\nSYSTEM You are an unhelpful so-called \"assistant\".")
            async def create():
                status_row = None
                status_label = None
                with self.creation_card:
                    status_row = ui.row()
                with status_row:
                    ui.label(f"Creating {model_name}...")
                    status_label = ui.label()
                try:
                    async for progress in await self.ollama.create(model=model_name, modelfile=modelfile.value, stream=True):
                        status_label.set_text(progress.status)
                    ui.notify(f"Created model {model_name}", type="positive")
                    dialog.close()
                except Exception as e:
                    ui.notify(f"Failed to create model: {str(e)}", type="negative")
                status_row.delete()
                await self.refresh_models_list()
            with ui.row():
                ui.button("Create", on_click=create, color="green")
                ui.button("Cancel", on_click=dialog.close)
        dialog.open()

    async def show_model_info(self, evt):
        model_name = evt.args
        with ui.dialog() as dialog, ui.card().style("max-width: none"):
            try:
                info = await self.ollama.show(model=model_name)
                with ui.grid(columns="auto 1fr"):
                    ui.label("Model")
                    ui.label(model_name)
                    ui.label("Modified")
                    ui.label(info.modified_at)
                    ui.label("Template")
                    ui.label(info.template).style("white-space: pre-wrap;")
                    ui.label("Modelfile")
                    ui.label(info.modelfile).style("white-space: pre-wrap;")
                    ui.label("License")
                    ui.label(info.license).style("white-space: pre-wrap;")
                    if info.details:
                        ui.label("Parent Model")
                        ui.label(info.details.parent_model)
                        ui.label("Format")
                        ui.label(info.details.format)
                        ui.label("Family")
                        ui.label(info.details.family)
                        ui.label("Families")
                        ui.label(", ".join(info.details.families))
                        ui.label("Parameter Size")
                        ui.label(info.details.parameter_size)
                        ui.label("Quantization Level")
                        ui.label(info.details.quantization_level)
                    ui.label("Parameters")
                    ui.label(info.parameters).style("white-space: pre-wrap;")
                    for k, v in info.modelinfo.items():
                        ui.label(k)
                        ui.label(str(v)).style("white-space: pre-wrap;")
            except Exception as e:
                ui.label(f"Failed to get model info: {str(e)}")
            ui.button("Close", on_click=dialog.close)
        dialog.open()

parser = argparse.ArgumentParser()
parser.add_argument("ollama", help="Ollama URL")
parser.add_argument("--refresh-interval", type=int, default=60, help="Refresh interval in seconds")
args = parser.parse_args()
OllamaManagementUI(args.ollama, args.refresh_interval).run()
