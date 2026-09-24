"""VOLTA — Unreal Engine Remote Execution Client.

Connects to running Unreal Engine editor instances via Unreal's built-in
Python Remote Execution protocol (UDP multicast discovery + TCP command socket).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from volta.unreal.remote_execution import (
    RemoteExecution,
    RemoteExecutionConfig,
    MODE_EXEC_FILE,
    MODE_EXEC_STATEMENT,
    MODE_EVAL_STATEMENT,
)

logger = logging.getLogger(__name__)


class UnrealRemoteClient:
    """High-level client for controlling a running Unreal Engine 5 editor."""

    def __init__(
        self,
        multicast_bind_address: str = "127.0.0.1",
        multicast_group_endpoint: tuple[str, int] = ("239.0.0.1", 6766),
    ):
        config = RemoteExecutionConfig()
        config.multicast_bind_address = multicast_bind_address
        config.multicast_group_endpoint = multicast_group_endpoint
        self._remote = RemoteExecution(config)
        self._connected = False
        self._node_id: Optional[str] = None

    def connect(self, timeout_sec: float = 3.0) -> bool:
        """Start discovery and connect to the first available Unreal Editor node."""
        self._remote.start()
        start = time.time()
        while time.time() - start < timeout_sec:
            nodes = self._remote.remote_nodes
            if nodes:
                node = nodes[0]
                self._node_id = node.get("node_id")
                self._remote.open_command_connection(self._node_id)
                self._connected = True
                logger.info(f"Connected to Unreal Engine node: {node}")
                return True
            time.sleep(0.2)
        return False

    def disconnect(self) -> None:
        """Close command connection and stop discovery."""
        if self._connected and self._node_id:
            try:
                self._remote.close_command_connection()
            except Exception:
                pass
        self._remote.stop()
        self._connected = False
        self._node_id = None

    def run_python(self, command: str, mode: str = MODE_EXEC_FILE) -> Dict[str, Any]:
        """Execute a Python statement or script inside Unreal Engine."""
        if not self._connected:
            if not self.connect():
                raise ConnectionError(
                    "Could not connect to Unreal Engine. Ensure UE is running and "
                    "Python Remote Execution is enabled in Project Settings."
                )
        return self._remote.run_command(command, exec_mode=mode)

    def export_assets(
        self,
        asset_paths: List[str],
        output_dir: Path,
        format_type: str = "FBX"
    ) -> List[Path]:
        """Batch export Unreal assets to disk as FBX or OBJ."""
        output_dir.mkdir(parents=True, exist_ok=True)
        py_script = f"""
import unreal
import os

asset_paths = {asset_paths}
output_dir = r"{str(output_dir)}"
exported = []

for path in asset_paths:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        print(f"Skipping unfound: {{path}}")
        continue
    
    asset_name = asset.get_name()
    out_file = os.path.join(output_dir, f"{{asset_name}}.{format_type.lower()}")
    
    task = unreal.AssetExportTask()
    task.object = asset
    task.filename = out_file
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    
    if "{format_type.upper()}" == "FBX":
        opt = unreal.FbxExportOption()
        opt.ascii = False
        opt.collision = False
        opt.level_of_detail = False
        task.options = opt
        
    success = unreal.Exporter.run_asset_export_task(task)
    if success:
        exported.append(out_file)
        print(f"Exported: {{out_file}}")
    else:
        print(f"Failed to export: {{path}}")

print(f"TOTAL_EXPORTED:{{len(exported)}}")
"""
        result = self.run_python(py_script)
        logger.debug(f"Export result: {result}")
        return list(output_dir.glob(f"*.{format_type.lower()}"))

    def capture_viewport(self, output_path: Path) -> bool:
        """Capture the active Unreal Editor viewport to an image file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        py_script = f"""
import unreal
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, r"{str(output_path)}")
print(f"Captured: {str(output_path)}")
"""
        result = self.run_python(py_script)
        return output_path.exists()
