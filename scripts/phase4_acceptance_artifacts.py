from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import fitz
import yaml

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.renderer import render_pdf, render_png
from ocop_pack.engine.scene import scene_from_manifest
from ocop_pack.engine.typography import resolve_candidate_typography
from ocop_pack.services.qa_service import qa_candidate
from ocop_pack.services.validation_service import load_project

ROOT = Path("data/runs_acceptance/phase4_typography")
BASE = Path("examples/projects/tea_basic")

PROJECTS = {
    "honey": {
        "project_id": "phase4_honey_acceptance",
        "product": {
            "name": "Mật ong hoa cà phê Đắk Lắk",
            "category": "Mật ong nguyên chất",
            "net_content": "250 g",
            "ingredients": (
                "Mật ong hoa cà phê Đắk Lắk nguyên chất, vị ngọt dịu, hậu hương thơm ấm."
            ),
            "usage_instructions": "Dùng trực tiếp hoặc pha với nước ấm dưới 40 độ C.",
            "storage_instructions": "Bảo quản nơi khô ráo, tránh ánh nắng trực tiếp.",
            "expiry_or_shelf_life": "24 tháng kể từ ngày sản xuất",
        },
        "producer": {
            "manufacturer_name": "Hợp tác xã Mật Ong Núi Xanh",
            "manufacturer_address": "Xã Ea Tu, Đắk Lắk, Việt Nam",
            "contact_phone": "0900000001",
        },
        "origin_text": "Sản phẩm OCOP của Đắk Lắk, đóng gói tại Việt Nam",
        "creative_brief_raw": "Tông mật ong ấm, gợi hoa cà phê và vùng cao nguyên.",
    },
    "matcha": {
        "project_id": "phase4_matcha_acceptance",
        "product": {
            "name": "Matcha Tân Cương",
            "category": "Bột trà xanh",
            "net_content": "100 g",
            "ingredients": (
                "Lá trà xanh Thái Nguyên nghiền mịn, màu xanh tự nhiên, hương vị thanh dịu."
            ),
            "usage_instructions": "Pha 2 g với nước ấm hoặc dùng làm bánh, đồ uống.",
            "storage_instructions": "Đậy kín sau khi mở, bảo quản nơi khô mát.",
            "expiry_or_shelf_life": "18 tháng kể từ ngày sản xuất",
        },
        "producer": {
            "manufacturer_name": "Hợp tác xã Trà Xanh Tân Cương",
            "manufacturer_address": "Tân Cương, Thái Nguyên, Việt Nam",
            "contact_phone": "0900000002",
        },
        "origin_text": "Sản phẩm OCOP của Thái Nguyên, đóng gói tại Việt Nam",
        "creative_brief_raw": "Tông matcha xanh dịu, sạch, cao cấp và gần gũi thiên nhiên.",
    },
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_project(kind: str, out: Path) -> Path:
    base = yaml.safe_load((BASE / "project.yaml").read_text(encoding="utf-8"))
    base.update(PROJECTS[kind])
    base["branding"] = {
        "logos": [
            {
                "asset_id": "brand",
                "path": str((BASE / "assets/brand.png").resolve()),
                "asset_type": "png",
                "role": "brand",
            }
        ],
        "ocop": {"logo_path": str((BASE / "assets/ocop.png").resolve()), "star_count": 3},
    }
    base["packaging"] = {
        "size_id": "OCOP_130X150",
        "qr_payload": f"https://example.com/ocop/{base['project_id']}",
    }
    path = out / "project_spec.yaml"
    path.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for kind in PROJECTS:
        run = ROOT / kind
        if run.exists():
            shutil.rmtree(run)
        run.mkdir(parents=True)
        project_path = write_project(kind, run)
        project = load_project(project_path)
        dieline = load_dieline(project.packaging.size_id)
        candidate = generate_candidates(project, dieline)[0]
        manifest = LayoutManifest(
            run_id=f"phase4_{kind}_acceptance",
            project_id=project.project_id,
            dieline_version=dieline.version,
            candidate=candidate,
        )
        scene = scene_from_manifest(manifest, dieline.width_mm, dieline.height_mm)
        png = render_png(scene, project, run / "packaging.png", dpi=150)
        pdf = render_pdf(scene, project, run / "packaging.pdf")
        doc = fitz.open(pdf)
        extracted = doc[0].get_text()
        pix = doc[0].get_pixmap(dpi=150, alpha=False)
        raster = run / "packaging_pdf_raster.png"
        pix.save(raster)
        doc.close()
        typography = {
            k: v.model_dump(mode="json")
            for k, v in resolve_candidate_typography(project, candidate, dpi=150).items()
        }
        qa = qa_candidate(manifest.run_id, project, dieline, candidate, png)
        (run / "selected_candidate.json").write_text(
            candidate.model_dump_json(indent=2), encoding="utf-8"
        )
        (run / "layout_manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        (run / "typography_metadata.json").write_text(
            json.dumps(typography, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (run / "qa_report.json").write_text(qa.model_dump_json(indent=2), encoding="utf-8")
        (run / "pdf_extracted_text.txt").write_text(extracted, encoding="utf-8")
        review = (
            "Print packaging.pdf at 100% / actual size. Disable fit-to-page/scaling. "
            "Verify Vietnamese accents, side-panel readability, and physical 1:1 "
            "dimensions with a ruler.\n"
        )
        (run / "PRINT_1_TO_1_REVIEW.md").write_text(review, encoding="utf-8")
        manifest_hashes = {
            p.name: sha(p)
            for p in sorted(run.iterdir())
            if p.is_file() and p.name != "artifact_sha256_manifest.json"
        }
        (run / "artifact_sha256_manifest.json").write_text(
            json.dumps(manifest_hashes, indent=2), encoding="utf-8"
        )
        print(kind, run, json.dumps(manifest_hashes, indent=2))


if __name__ == "__main__":
    main()
