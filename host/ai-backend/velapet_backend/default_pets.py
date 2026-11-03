"""Original editable vector pets; deterministic local PNG exports, no AI calls."""
from functools import lru_cache
import hashlib
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
import resvg_py

from .store import owner_key

SOURCE = Path(__file__).resolve().parents[3] / "assets" / "source" / "default-pets"
PETS = {
    "nova-cat": {"name": "星云猫", "description": "安静温暖的紫色小猫", "persona_id": "nova"},
    "biscuit-dog": {"name": "奶油犬", "description": "活泼友好的奶油色小犬", "persona_id": "spark"},
    "mint-rabbit": {"name": "薄荷兔", "description": "耐心温柔的薄荷色小兔", "persona_id": "nova"},
}
SIZES = {"avatar": 128, "home": 240, "skin": 160}


@lru_cache(maxsize=9)
def render_pet(pet_id: str, kind: str) -> bytes:
    if pet_id not in PETS or kind not in SIZES:
        raise KeyError("Unknown built-in asset")
    return resvg_py.svg_to_bytes(svg_path=str(SOURCE / (pet_id + ".svg")),
                                 width=SIZES[kind], height=SIZES[kind], skip_system_fonts=True)


def pet_catalog():
    return [{"id": pid, **pet, "source": "builtin_vector", "artifacts": [
        {"kind": kind, "width": size, "height": size, "mime_type": "image/png",
         "byte_size": len(render_pet(pid, kind)), "sha256": hashlib.sha256(render_pet(pid, kind)).hexdigest(),
         "download_url": f"/api/v1/default-pets/{pid}/{kind}.png"}
        for kind, size in SIZES.items()]} for pid, pet in PETS.items()]


class AppearanceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    pet_id: Literal["nova-cat", "biscuit-dog", "mint-rabbit"]


def default_pet_router(store, auth):
    router = APIRouter(dependencies=[Depends(auth)])

    @router.get("/api/v1/default-pets")
    def catalog():
        return {"default_pet_id": "nova-cat", "pets": pet_catalog()}

    @router.get("/api/v1/default-pets/{pet_id}/{kind}.png")
    def image(pet_id: str, kind: str):
        try:
            raw = render_pet(pet_id, kind)
        except KeyError:
            raise HTTPException(404)
        return Response(raw, media_type="image/png",
                        headers={"ETag": '"' + hashlib.sha256(raw).hexdigest() + '"'})

    @router.get("/api/v1/appearance")
    def appearance(device_id: str, x_velapet_token: str | None = Header(None)):
        pid = store.appearance(owner_key(x_velapet_token, device_id))
        return {"pet_id": pid, "source": "builtin_vector"}

    @router.put("/api/v1/appearance")
    def select(body: AppearanceRequest, x_velapet_token: str | None = Header(None)):
        store.save_appearance(owner_key(x_velapet_token, body.device_id), body.pet_id)
        # Appearance is independent of growth skins, personality and EXP.
        return {"pet_id": body.pet_id, "source": "builtin_vector"}

    return router
