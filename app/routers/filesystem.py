import os
import re
import string
import subprocess

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models import User
from app.security import require_admin

router = APIRouter(prefix="/api/admin/filesystem", tags=["filesystem"])


class FolderEntry(BaseModel):
    name: str
    path: str


class BrowseFoldersOut(BaseModel):
    path: str | None
    parentPath: str | None
    folders: list[FolderEntry]


def _local_drive_roots() -> list[FolderEntry]:
    roots = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            roots.append(FolderEntry(name=drive, path=drive))
    return roots


_DRIVE_ROOT_RE = re.compile(r"^[A-Za-z]:\\?$")
_UNC_HOST_ONLY_RE = re.compile(r"^\\\\([^\\]+)\\?$")


def _list_shares(host: str) -> list[FolderEntry]:
    """A bare `\\host` isn't itself an openable directory on Windows - you can
    only browse into `\\host\ShareName`. `net view` is what actually knows
    which share names a host is offering, so it's used here to make typing
    just the server address behave like a real browsable level instead of
    erroring out."""
    try:
        result = subprocess.run(
            ["net", "view", f"\\\\{host}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=400, detail=f"Could not reach \\\\{host}: {exc}") from exc

    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "host unreachable or not sharing anything"
        raise HTTPException(status_code=400, detail=f"Could not list shares on \\\\{host} - {reason}")

    lines = result.stdout.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.strip().startswith("Share name")), None)
    if header_idx is None:
        return []

    header = lines[header_idx]
    type_col = header.index("Type")
    used_col = header.index("Used as")

    shares = []
    for line in lines[header_idx + 2 :]:
        if not line.strip() or line.startswith("The command completed"):
            break
        name = line[:type_col].strip()
        share_type = line[type_col:used_col].strip()
        if name and share_type.lower() == "disk":
            shares.append(FolderEntry(name=name, path=f"\\\\{host}\\{name}"))
    return shares


@router.get("/browse", response_model=BrowseFoldersOut)
def browse_folders(
    path: str | None = None,
    current_user: User = Depends(require_admin),
):
    """Lists subfolders under `path` so an admin can pick a source folder by
    clicking through it instead of typing a UNC path by hand. With no `path`,
    returns local drive roots as starting points - from there the admin can
    type a UNC host or share (e.g. \\\\server or \\\\server\\share) directly
    into the address bar and browse into it."""
    if not path:
        return BrowseFoldersOut(path=None, parentPath=None, folders=_local_drive_roots())

    host_only = _UNC_HOST_ONLY_RE.match(path.strip())
    if host_only:
        host = host_only.group(1)
        normalized = f"\\\\{host}"
        return BrowseFoldersOut(path=normalized, parentPath="", folders=_list_shares(host))

    normalized = os.path.normpath(path)
    if not os.path.isdir(normalized):
        raise HTTPException(
            status_code=400,
            detail="That folder does not exist or is not accessible - if this is a server address, "
            "include the share name too (e.g. \\\\server\\ShareName)",
        )

    try:
        entries = sorted(os.scandir(normalized), key=lambda e: e.name.lower())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Access denied for that folder") from exc

    folders = [
        FolderEntry(name=e.name, path=os.path.join(normalized, e.name))
        for e in entries
        if e.is_dir(follow_symlinks=False)
    ]

    if _DRIVE_ROOT_RE.match(normalized):
        parent = ""  # "Up" from a drive root goes back to the drive list
    else:
        candidate = os.path.dirname(normalized)
        parent = None if candidate == normalized else candidate  # UNC share root has no parent

    return BrowseFoldersOut(path=normalized, parentPath=parent, folders=folders)
