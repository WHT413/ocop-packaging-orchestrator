from __future__ import annotations

from hashlib import sha256

from ocop_pack.agents.visual_critic.schemas import CandidateAestheticScore, CriticDecision
from ocop_pack.application.ports.vision_critic import CriticRequest, CriticResult
from ocop_pack.provenance.models import CriticProvenance, ProviderContext


class MockVisualCriticProvider:
    provider = "mock"
    model = "mock-critic-v1"

    def evaluate(self, request: CriticRequest, context: ProviderContext) -> CriticResult:
        poor = any("poor" in cid.lower() or "bad" in cid.lower() for cid in request.candidate_ids)
        selected = None if poor else sorted(request.candidate_ids)[0]
        scores = [
            CandidateAestheticScore(
                candidate_id=candidate_id,
                readability_hierarchy=3.0 if poor else 8.0,
                balance_whitespace=3.0 if poor else 8.0,
                brand_fit=4.0 if poor else 8.0,
                artwork_relevance=4.0 if poor else 8.0,
                distinctiveness=3.0 if poor else 7.0,
                total_score=3.4 if poor else 7.9,
                summary="Scripted mock requires review for poor packaging fixture."
                if poor
                else "Offline deterministic structural score.",
            )
            for candidate_id in request.candidate_ids
        ]
        decision = CriticDecision(
            schema_version=request.schema_version,
            status="HUMAN_REVIEW" if poor else "PASS",
            selected_candidate_id=selected,
            candidate_scores=scores,
            targeted_revision=None,
            confidence=0.8,
            decision_summary="Scripted mock requires review for poor packaging fixture."
            if poor
            else "Mock critic selected the best deterministic structural candidate.",
        )
        decision_hash = sha256(decision.model_dump_json().encode("utf-8")).hexdigest()
        provenance = CriticProvenance(
            contact_sheet_hash=request.contact_sheet_hash,
            candidate_hashes=request.candidate_hashes,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            rubric_version=request.rubric_version,
            schema_version=request.schema_version,
            provider=self.provider,
            model=self.model,
            provider_request_id=f"mock-{context.run_id}",
            decision_hash=decision_hash,
            raw_response_hash=decision_hash,
        )
        return CriticResult(
            decision=decision,
            provider=self.provider,
            model_id=self.model,
            provider_request_id=provenance.provider_request_id,
            contact_sheet_hash=request.contact_sheet_hash,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            schema_version=request.schema_version,
            raw_response_hash=decision_hash,
            provenance=provenance,
        )
