"""ClinicalTrials.gov subagent for upcoming trial readouts."""

from datetime import datetime, timedelta
from typing import Any

from .base_agent import BaseAgent

# Hot therapeutic areas for M&A
HOT_AREAS = [
    "obesity", "glp-1", "glp1", "weight loss",
    "oncology", "cancer", "tumor",
    "adc", "antibody drug conjugate",
    "radiopharmaceutical", "radioligand",
    "autoimmune", "immunology",
    "neuropsychiatry", "cns", "depression", "schizophrenia",
    "nash", "mash", "liver",
    "rare disease", "orphan"
]


class ClinicalTrialsAgent(BaseAgent):
    """Agent that fetches Phase 2/3 trials nearing completion."""

    def __init__(self, phases: list[str] | None = None, months_ahead: int = 12):
        super().__init__("ClinicalTrials")
        self.phases = phases or ["PHASE2", "PHASE3"]
        self.months_ahead = months_ahead
        self.api_url = "https://clinicaltrials.gov/api/v2/studies"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch trials nearing completion."""
        all_trials = []

        for phase in self.phases:
            params = {
                "query.term": "obesity OR cancer OR oncology OR autoimmune OR neuropsychiatry",
                "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING",
                "filter.phase": phase,
                "pageSize": "50",
                "sort": "LastUpdatePostDate:desc"
            }

            try:
                resp = await self.client.get(self.api_url, params=params)
                resp.raise_for_status()
                data = resp.json()

                for study in data.get("studies", []):
                    protocol = study.get("protocolSection", {})
                    identification = protocol.get("identificationModule", {})
                    status = protocol.get("statusModule", {})
                    design = protocol.get("designModule", {})
                    sponsor = protocol.get("sponsorCollaboratorsModule", {})
                    conditions = protocol.get("conditionsModule", {})
                    interventions = protocol.get("armsInterventionsModule", {})

                    completion_date = status.get("primaryCompletionDateStruct", {}).get("date")

                    all_trials.append({
                        "source": "clinical_trials",
                        "nct_id": identification.get("nctId"),
                        "title": identification.get("briefTitle"),
                        "sponsor": sponsor.get("leadSponsor", {}).get("name"),
                        "phase": ", ".join(design.get("phases", [])),
                        "status": status.get("overallStatus"),
                        "completion_date": completion_date,
                        "conditions": conditions.get("conditions", []),
                        "interventions": [
                            i.get("name") for i in interventions.get("interventions", [])
                        ]
                    })
            except Exception:
                continue

        return all_trials

    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter for trials in hot therapeutic areas with near-term readouts."""
        relevant = []
        cutoff = datetime.now() + timedelta(days=self.months_ahead * 30)

        for trial in data:
            # Check if completion date is within window
            completion = trial.get("completion_date")
            if completion:
                try:
                    # Parse various date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m", "%B %Y", "%Y"]:
                        try:
                            comp_date = datetime.strptime(completion, fmt)
                            if comp_date > cutoff:
                                continue
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            # Check for hot therapeutic areas
            text = f"{' '.join(trial.get('conditions', []))} {trial.get('title', '')}".lower()

            if any(area in text for area in HOT_AREAS):
                # Prioritize industry-sponsored trials (more likely M&A targets)
                sponsor = trial.get("sponsor", "").lower()
                is_industry = not any(
                    x in sponsor for x in ["university", "hospital", "institute", "nih", "national"]
                )
                trial["industry_sponsored"] = is_industry
                relevant.append(trial)

        # Sort by industry sponsorship and completion date
        relevant.sort(key=lambda x: (not x.get("industry_sponsored", False), x.get("completion_date", "9999")))

        return relevant[:30]
