"""VOLTA — Fab & Megascans Library Ingest and Exporter.

Scans local Fab download directories, catalogs 3D meshes and PBR texture maps,
and routes them into project production directories (e.g., Bear Suit Man, Cuddle Pirates).
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_FAB_CACHE = Path(r"E:\data\Unreal_Fab_Library\VaultCache\FabLibrary")


class FabLibrary:
    """Manager for downloaded Fab and Megascans library assets."""

    def __init__(self, cache_dir: Path = DEFAULT_FAB_CACHE):
        self.cache_dir = Path(cache_dir)

    def scan(self) -> List[Dict[str, Any]]:
        """Scan the cache directory and return an inventory of all downloaded assets."""
        if not self.cache_dir.exists():
            return []

        inventory = []
        for entry in sorted(self.cache_dir.iterdir()):
            if not entry.is_dir():
                continue

            item = {
                "id": entry.name,
                "title": entry.name.split("-")[0].replace("_", " "),
                "path": str(entry),
                "formats": [],
                "meshes": [],
                "textures": [],
                "thumbnail": None,
            }

            for child in entry.iterdir():
                if child.is_dir():
                    item["formats"].append(child.name)

            for thumb in entry.rglob("thumbnail.*"):
                item["thumbnail"] = str(thumb)
                break

            for ext in ("*.fbx", "*.gltf", "*.obj"):
                for mesh in entry.rglob(ext):
                    item["meshes"].append({
                        "name": mesh.name,
                        "path": str(mesh),
                        "size_mb": round(mesh.stat().st_size / (1024 * 1024), 2),
                    })

            for tex in entry.rglob("*.*"):
                if tex.suffix.lower() in (".png", ".jpg", ".jpeg", ".exr", ".tga"):
                    if "thumbnail" not in tex.name.lower():
                        item["textures"].append({
                            "name": tex.name,
                            "path": str(tex),
                            "size_mb": round(tex.stat().st_size / (1024 * 1024), 2),
                        })

            inventory.append(item)
        return inventory

    def export_to_project(
        self,
        asset_id: str,
        destination_dir: Path,
        copy_textures: bool = True
    ) -> Dict[str, Any]:
        """Export an asset's 3D mesh and PBR textures directly into a project folder."""
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        inventory = self.scan()
        matched = [i for i in inventory if asset_id.lower() in i["id"].lower() or asset_id.lower() in i["title"].lower()]
        if not matched:
            raise FileNotFoundError(f"Asset '{asset_id}' not found in Fab library.")

        asset = matched[0]
        copied_meshes = []
        copied_textures = []

        for mesh in asset["meshes"]:
            src = Path(mesh["path"])
            dst = destination_dir / src.name
            shutil.copy2(src, dst)
            copied_meshes.append(str(dst))

        if copy_textures:
            tex_dir = destination_dir / "textures"
            tex_dir.mkdir(exist_ok=True)
            for tex in asset["textures"]:
                src = Path(tex["path"])
                dst = tex_dir / src.name
                shutil.copy2(src, dst)
                copied_textures.append(str(dst))

        return {
            "title": asset["title"],
            "destination": str(destination_dir),
            "meshes": copied_meshes,
            "textures": copied_textures,
        }
