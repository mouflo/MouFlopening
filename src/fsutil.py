"""Copie et déplacement de fichiers tolérants au NAS (partages réseau : droits et dates parfois non modifiables)."""

import os
import shutil
from pathlib import Path


def safe_copy(src, dst) -> None:
    """Copie le contenu (les dates sont copiées si possible, sans erreur sinon)."""
    shutil.copyfile(src, dst)
    try:
        shutil.copystat(src, dst)
    except OSError:
        pass


def safe_move(src, dst) -> None:
    """
    Déplace src vers dst, même d'un disque à l'autre et même si dst existe déjà sur un NAS.
    Le fichier est copié à côté de la destination puis renommé : jamais de fichier à moitié écrit.
    """
    src, dst = Path(src), Path(dst)
    try:
        os.replace(src, dst)
        return
    except OSError:
        pass
    tmp = dst.with_name(dst.name + ".partiel")
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    src.unlink()
