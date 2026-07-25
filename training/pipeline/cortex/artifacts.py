from __future__ import annotations

import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA = "ninereeds_campaign_registry_v1"
MANIFEST_SCHEMA = "ninereeds_campaign_manifest_v1"
_CAMPAIGN_DIR = re.compile(r"campaign_(\d+)_reports$")


class CampaignArtifactError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class CampaignRegistry:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.logs_root = self.repo_root / "training/logs"
        self.path = self.logs_root / "campaign_registry.json"

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": REGISTRY_SCHEMA,
                "updated_at": utc_now(),
                "campaigns": [],
            }
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != REGISTRY_SCHEMA
            or not isinstance(value.get("campaigns"), list)
        ):
            raise CampaignArtifactError("invalid campaign registry")
        return value

    def get_or_allocate(
        self,
        *,
        campaign_id: str,
        objective: str,
        created_at: str | None,
        preferred_number: int | None = None,
    ) -> dict[str, Any]:
        registry = self.read()
        for entry in registry["campaigns"]:
            if entry.get("campaign_id") == campaign_id:
                return entry
        used = {
            int(entry["number"])
            for entry in registry["campaigns"]
            if isinstance(entry.get("number"), int)
        }
        if self.logs_root.is_dir():
            for path in self.logs_root.iterdir():
                match = _CAMPAIGN_DIR.fullmatch(path.name)
                if match:
                    used.add(int(match.group(1)))
        number = preferred_number
        if number is None:
            number = max(used | {0}) + 1
        if number in used:
            raise CampaignArtifactError(f"campaign number is already allocated: {number}")
        entry = {
            "number": number,
            "campaign_id": campaign_id,
            "display_name": f"{number}: {campaign_id}",
            "objective": objective,
            "created_at": created_at or utc_now(),
            "artifact_root": f"training/logs/campaign_{number}_reports",
            "status": "running",
            "updated_at": utc_now(),
        }
        registry["campaigns"].append(entry)
        registry["campaigns"].sort(key=lambda row: int(row["number"]))
        registry["updated_at"] = utc_now()
        _write_json(self.path, registry)
        return entry

    def update_status(self, campaign_id: str, status: str) -> None:
        registry = self.read()
        changed = False
        for entry in registry["campaigns"]:
            if entry.get("campaign_id") == campaign_id:
                if entry.get("status") != status:
                    entry["status"] = status
                    entry["updated_at"] = utc_now()
                    changed = True
                break
        if changed:
            registry["updated_at"] = utc_now()
            _write_json(self.path, registry)


class CortexCampaignPublisher:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.registry = CampaignRegistry(self.repo_root)

    def publish_evaluation(
        self,
        *,
        campaign_state: dict[str, Any],
        source_plan_id: str,
        evaluation: dict[str, Any],
        preferred_number: int | None = None,
    ) -> dict[str, Any]:
        campaign_id = str(campaign_state["campaign_id"])
        entry = self.registry.get_or_allocate(
            campaign_id=campaign_id,
            objective=str(campaign_state["objective"]),
            created_at=campaign_state.get("created_at"),
            preferred_number=preferred_number,
        )
        root = self.repo_root / entry["artifact_root"]
        manifest_path = root / "00_manifest.json"
        manifest = self._manifest(entry, campaign_state, manifest_path)
        if source_plan_id in manifest["source_plan_ids"]:
            return {
                "changed": False,
                "campaign_number": entry["number"],
                "artifact_root": entry["artifact_root"],
            }

        candidate = evaluation["candidate"]
        certificate = evaluation["certificate"]
        stem = Path(certificate["candidate_checkpoint"]).stem
        evaluation_relative = f"evaluations/{stem}.json"
        transcript_relative = f"transcripts/{stem}.jsonl"
        _write_json(root / evaluation_relative, evaluation)
        transcript = "\n".join(
            json.dumps(
                {
                    "case_id": row["case_id"],
                    "group": row["group"],
                    "concept": row["concept"],
                    "language": row["language"],
                    "prompt": row["prompt"],
                    "expected_response": row["expected_response"],
                    "response": row["response"],
                    "score": row["score"],
                    "passed": row["passed"],
                    "heldout_loss": row["heldout_loss"],
                    "repetition": row["repetition"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            for row in candidate["cases"]
        )
        _atomic_write(root / transcript_relative, transcript + "\n")

        manifest["source_plan_ids"].append(source_plan_id)
        manifest["evaluations"].append(
            {
                "source_plan_id": source_plan_id,
                "candidate_checkpoint": certificate["candidate_checkpoint"],
                "parent_checkpoint": certificate["parent_checkpoint"],
                "status": certificate["status"],
                "overall_score": certificate["overall_score"],
                "target_score": certificate["target_score"],
                "protected_score": certificate["protected_score"],
                "evaluation": evaluation_relative,
                "transcript": transcript_relative,
                "published_at": utc_now(),
            }
        )
        manifest["evaluations"].sort(
            key=lambda row: (
                self._checkpoint_sequence(str(row["candidate_checkpoint"])),
                str(row["published_at"]),
            )
        )
        manifest["updated_at"] = utc_now()
        manifest["campaign_status"] = campaign_state["status"]
        manifest["winner"] = self._winner(manifest["evaluations"])
        _write_json(manifest_path, manifest)
        latest = self._latest_evaluation(root, manifest)
        assert latest is not None
        self._write_latest_artifacts(root, manifest, latest)
        self.registry.update_status(campaign_id, str(campaign_state["status"]))
        return {
            "changed": True,
            "campaign_number": entry["number"],
            "artifact_root": entry["artifact_root"],
            "winner": manifest["winner"],
        }

    def finalize(self, campaign_state: dict[str, Any]) -> dict[str, Any] | None:
        registry = self.registry.read()
        entry = next(
            (
                row
                for row in registry["campaigns"]
                if row.get("campaign_id") == campaign_state.get("campaign_id")
            ),
            None,
        )
        if entry is None:
            return None
        root = self.repo_root / entry["artifact_root"]
        manifest_path = root / "00_manifest.json"
        if not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = (
            manifest.get("campaign_status") != campaign_state.get("status")
            or manifest.get("stop_reason") != campaign_state.get("stop_reason")
        )
        if changed:
            manifest["campaign_status"] = campaign_state["status"]
            manifest["stop_reason"] = campaign_state.get("stop_reason")
            manifest["updated_at"] = utc_now()
            _write_json(manifest_path, manifest)
            latest = self._latest_evaluation(root, manifest)
            if latest is not None:
                self._write_latest_artifacts(root, manifest, latest)
        self.registry.update_status(
            str(campaign_state["campaign_id"]), str(campaign_state["status"])
        )
        return {
            "changed": changed,
            "campaign_number": entry["number"],
            "artifact_root": entry["artifact_root"],
        }

    @staticmethod
    def _manifest(
        entry: dict[str, Any],
        state: dict[str, Any],
        path: Path,
    ) -> dict[str, Any]:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema_version") != MANIFEST_SCHEMA:
                raise CampaignArtifactError("invalid campaign manifest")
            return value
        return {
            "schema_version": MANIFEST_SCHEMA,
            "campaign_number": entry["number"],
            "campaign_id": entry["campaign_id"],
            "display_name": entry["display_name"],
            "objective": state["objective"],
            "campaign_status": state["status"],
            "stop_reason": state.get("stop_reason"),
            "created_at": state.get("created_at") or utc_now(),
            "updated_at": utc_now(),
            "source_plan_ids": [],
            "evaluations": [],
            "winner": None,
        }

    @staticmethod
    def _winner(evaluations: list[dict[str, Any]]) -> dict[str, Any] | None:
        admitted = [row for row in evaluations if row["status"] == "admitted"]
        if not admitted:
            return None
        best = max(
            admitted,
            key=lambda row: (
                float(row["overall_score"]),
                float(row["target_score"]),
                float(row["protected_score"]),
            ),
        )
        return {
            "checkpoint": best["candidate_checkpoint"],
            "source_plan_id": best["source_plan_id"],
            "overall_score": best["overall_score"],
            "target_score": best["target_score"],
            "protected_score": best["protected_score"],
        }

    @staticmethod
    def _latest_evaluation(
        root: Path, manifest: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not manifest["evaluations"]:
            return None
        path = root / manifest["evaluations"][-1]["evaluation"]
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _checkpoint_sequence(value: str) -> int:
        match = re.search(r"(?:block|checkpoint)[_-](\d+)", value, re.IGNORECASE)
        return int(match.group(1)) if match else -1

    def _write_latest_artifacts(
        self,
        root: Path,
        manifest: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> None:
        certificate = evaluation["certificate"]
        metrics = {
            "schema_version": "ninereeds_campaign_metrics_v1",
            "campaign_number": manifest["campaign_number"],
            "campaign_id": manifest["campaign_id"],
            "suite_id": evaluation["suite_id"],
            "candidate_checkpoint": certificate["candidate_checkpoint"],
            "candidate": evaluation["candidate"]["summary"],
            "parent_checkpoint": certificate["parent_checkpoint"],
            "parent": evaluation["parent"]["summary"],
            "certificate": certificate,
            "winner": manifest["winner"],
            "updated_at": utc_now(),
        }
        decision = {
            "schema_version": "ninereeds_campaign_decision_v1",
            "campaign_number": manifest["campaign_number"],
            "campaign_id": manifest["campaign_id"],
            "candidate_checkpoint": certificate["candidate_checkpoint"],
            "decision": certificate["status"],
            "reasons": certificate["reasons"],
            "failure_modes": certificate.get("failure_modes", []),
            "recommended_next_action": certificate.get("recommended_next_action"),
            "recommended_parent_checkpoint": certificate[
                "recommended_parent_checkpoint"
            ],
            "winner": manifest["winner"],
            "updated_at": utc_now(),
        }
        retention = {
            "schema_version": "ninereeds_campaign_retention_manifest_v1",
            "campaign_number": manifest["campaign_number"],
            "campaign_id": manifest["campaign_id"],
            "winner": manifest["winner"],
            "always_retain": sorted(
                {
                    certificate["recommended_parent_checkpoint"],
                    certificate["rollback_target"],
                    *(
                        [manifest["winner"]["checkpoint"]]
                        if manifest["winner"] is not None
                        else []
                    ),
                }
            ),
            "latest_candidate": {
                "path": certificate["candidate_checkpoint"],
                "state": certificate["status"],
            },
            "policy": "training/pipeline/cortex/retention_policy.json",
            "updated_at": utc_now(),
        }
        _write_json(root / "metrics.json", metrics)
        _write_json(root / "decision.json", decision)
        _write_json(root / "retention_manifest.json", retention)
        _atomic_write(root / "01_report.md", self._report_markdown(manifest, evaluation))
        _atomic_write(root / "cortex_mri.html", self._render_mri(manifest, evaluation))
        _atomic_write(
            root / "cortex_3d_map.html", self._render_graph(manifest, evaluation)
        )
        _atomic_write(
            root / "cortex_atlas.html", self._render_atlas(manifest, evaluation)
        )

    @staticmethod
    def _report_markdown(
        manifest: dict[str, Any], evaluation: dict[str, Any]
    ) -> str:
        certificate = evaluation["certificate"]
        candidate = evaluation["candidate"]["summary"]
        parent = evaluation["parent"]["summary"]
        winner = (
            manifest["winner"]["checkpoint"]
            if manifest["winner"] is not None
            else "No candidate has passed admission."
        )
        reasons = certificate["reasons"] or ["All deterministic admission gates passed."]
        reason_lines = "\n".join(f"- {reason}" for reason in reasons)
        next_action = certificate.get(
            "recommended_next_action",
            "No deterministic next action was recorded.",
        )
        return f"""# {manifest['display_name']}

**Status:** {manifest['campaign_status']}
**Objective:** {manifest['objective']}
**Latest candidate:** `{certificate['candidate_checkpoint']}`
**Admission:** `{certificate['status']}`
**Recommended next parent:** `{certificate['recommended_parent_checkpoint']}`
**Campaign winner:** {winner}

## Behavioral comparison

| Metric | Candidate | Parent |
| --- | ---: | ---: |
| Overall score | {candidate['overall']['score']:.3f} | {parent['overall']['score']:.3f} |
| Protected score | {candidate['groups']['protected']['score']:.3f} | {parent['groups']['protected']['score']:.3f} |
| Held-out loss | {candidate['heldout_loss']:.3f} | {parent['heldout_loss']:.3f} |
| Pathological outputs | {candidate['overall']['pathological']} / {candidate['overall']['total']} | {parent['overall']['pathological']} / {parent['overall']['total']} |

## Admission findings

{reason_lines}

## Recommended next action

{next_action}

## Research interpretation

Training loss is recorded only as an optimization-health signal. Admission is
determined from held-out generated behavior, protected regressions, repetition,
checkpoint lineage, and Cortex activation health. The MRI, 3D map, atlas,
machine-readable metrics, decision, and exact transcripts in this directory
belong to the same numbered campaign.
"""

    @staticmethod
    def _style(title: str) -> str:
        return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(title)}</title><style>
body{{background:#001008;color:#d9ffe4;font:15px ui-monospace,monospace;margin:24px}}
h1,h2{{color:#71ff9c}} .card{{border:1px solid #176c36;background:#031a0d;padding:16px;margin:12px 0}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #176c36;padding:7px;text-align:left}}
.bad{{color:#ff8d8d}}.good{{color:#71ff9c}}.bar{{height:10px;background:#19d466;display:inline-block}}
small{{color:#7ebd91}}canvas{{width:100%;height:620px;background:#000b05;border:1px solid #176c36}}
</style></head><body>"""

    def _render_mri(
        self, manifest: dict[str, Any], evaluation: dict[str, Any]
    ) -> str:
        scan = evaluation["candidate"]["scan"]["activation_health"]
        rows = []
        for layer in scan["layers"]:
            density = float(layer["xy_sparse_density"])
            rows.append(
                "<tr>"
                f"<td>{layer['tick']}</td><td>{layer['layer']}</td>"
                f"<td>{density:.6f}</td>"
                f"<td><span class='bar' style='width:{max(1, min(100, density * 200)):.1f}%'></span></td>"
                f"<td>{float(layer['xy_sparse_mean_abs']):.6f}</td>"
                "</tr>"
            )
        return (
            self._style(f"{manifest['display_name']} Cortex MRI")
            + f"<h1>{html.escape(manifest['display_name'])} — Cortex MRI</h1>"
            + "<div class='card'>"
            + f"Hidden mean |x|: {scan['hidden_mean_abs']:.6f} · "
            + f"hidden std: {scan['hidden_std']:.6f} · "
            + f"dead layers: {html.escape(str(scan['dead_layers']))} · "
            + f"saturated layers: {html.escape(str(scan['saturated_layers']))}"
            + "</div><table><thead><tr><th>Tick</th><th>Layer</th>"
            + "<th>xy density</th><th>relative activity</th><th>mean |xy|</th>"
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></body></html>"
        )

    def _render_graph(
        self, manifest: dict[str, Any], evaluation: dict[str, Any]
    ) -> str:
        points = json.dumps(
            evaluation["candidate"]["scan"]["points"]["core"],
            ensure_ascii=False,
        ).replace("</", "<\\/")
        return (
            self._style(f"{manifest['display_name']} 3D map")
            + f"<h1>{html.escape(manifest['display_name'])} — core representation map</h1>"
            + "<p>Drag horizontally to rotate. Color denotes concept; square points are protected anchors.</p>"
            + "<canvas id='map' width='1200' height='620'></canvas><script>"
            + f"const points={points};"
            + """const c=document.getElementById('map'),x=c.getContext('2d');
let angle=.45,drag=false,last=0;
const palette=['#64ff8f','#5bc0ff','#ffd65b','#ff6bd6','#c6ff5b','#ff8d71'];
const concepts=[...new Set(points.map(p=>p.concept))];
function draw(){x.clearRect(0,0,c.width,c.height);x.font='13px monospace';
points.map(p=>{const ca=Math.cos(angle),sa=Math.sin(angle),rx=p.x*ca-p.z*sa,rz=p.x*sa+p.z*ca;
return {...p,rx,rz};}).sort((a,b)=>a.rz-b.rz).forEach(p=>{
const scale=190/(2.4-p.rz),px=c.width/2+p.rx*scale*3,py=c.height/2-p.y*scale*3;
x.fillStyle=palette[concepts.indexOf(p.concept)%palette.length];
if(p.group==='protected'){x.fillRect(px-5,py-5,10,10)}else{x.beginPath();x.arc(px,py,6,0,Math.PI*2);x.fill()}
x.fillText(p.case_id,px+9,py+4);});}
c.onmousedown=e=>{drag=true;last=e.clientX};c.onmouseup=()=>drag=false;c.onmouseleave=()=>drag=false;
c.onmousemove=e=>{if(drag){angle+=(e.clientX-last)/180;last=e.clientX;draw()}};draw();
</script></body></html>"""
        )

    def _render_atlas(
        self, manifest: dict[str, Any], evaluation: dict[str, Any]
    ) -> str:
        health = evaluation["candidate"]["scan"]["representation_health"]
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(stage)}</td>"
            f"<td>{values['within_concept_cosine']:.5f}</td>"
            f"<td>{values['between_concept_cosine']:.5f}</td>"
            f"<td>{values['concept_separation']:.5f}</td>"
            "</tr>"
            for stage, values in health.items()
        )
        cases = "".join(
            "<tr>"
            f"<td>{html.escape(case['case_id'])}</td>"
            f"<td>{html.escape(case['concept'])}</td>"
            f"<td>{html.escape(case['language'])}</td>"
            f"<td class=\"{'good' if case['passed'] else 'bad'}\">{case['score']:.2f}</td>"
            f"<td>{html.escape(case['response'])}</td>"
            "</tr>"
            for case in evaluation["candidate"]["cases"]
        )
        return (
            self._style(f"{manifest['display_name']} Cortex atlas")
            + f"<h1>{html.escape(manifest['display_name'])} — Cortex atlas</h1>"
            + "<h2>Representation organization</h2><table><tr><th>Stage</th>"
            + "<th>Within-concept cosine</th><th>Between-concept cosine</th>"
            + "<th>Separation</th></tr>"
            + rows
            + "</table><h2>Behavioral traces</h2><table><tr><th>Probe</th>"
            + "<th>Concept</th><th>Language</th><th>Score</th><th>Response</th></tr>"
            + cases
            + "</table></body></html>"
        )
