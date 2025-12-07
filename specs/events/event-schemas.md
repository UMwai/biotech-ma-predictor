# Event Schema Specifications

**Version:** 1.0.0
**Last Updated:** 2025-12-07
**System:** Biotech M&A Predictor

---

## Table of Contents

1. [Overview](#overview)
2. [Message Envelope Format](#message-envelope-format)
3. [Event Schemas](#event-schemas)
   - [ClinicalTrialSignalEvent](#clinicaltrialsignalevent)
   - [PatentCliffEvent](#patentcliffevent)
   - [InsiderActivityEvent](#insideractivityevent)
   - [HiringSignalEvent](#hiringsignalevent)
   - [MACandidateEvent](#macandidateevent)
   - [AcquirerMatchEvent](#acquirermatchevent)
   - [ReportGeneratedEvent](#reportgeneratedevent)
4. [Validation Rules](#validation-rules)
5. [Event Flow](#event-flow)

---

## Overview

This document defines the event schemas used in the biotech M&A predictor system. All events flow through a common event bus and adhere to a standard message envelope format. Events are produced by three primary signal sources:

- **Clinical Trial Signals**: Trial outcomes, phase progressions, trial terminations
- **Patent IP Intelligence**: Patent expirations, generic entry threats, IP landscape changes
- **Insider & Hiring Signals**: Form 4/13F filings, executive movements, key hiring activities

These signals are processed to generate M&A candidate predictions and acquirer-target matches.

---

## Message Envelope Format

All events published to the event bus MUST be wrapped in a standard message envelope.

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "envelope_version",
    "event_id",
    "event_type",
    "event_version",
    "source",
    "timestamp",
    "payload"
  ],
  "properties": {
    "envelope_version": {
      "type": "string",
      "description": "Version of the envelope schema",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "example": "1.0.0"
    },
    "event_id": {
      "type": "string",
      "description": "Unique identifier for this event instance (UUID v4)",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
      "example": "550e8400-e29b-41d4-a716-446655440000"
    },
    "event_type": {
      "type": "string",
      "description": "Type of event being published",
      "enum": [
        "ClinicalTrialSignalEvent",
        "PatentCliffEvent",
        "InsiderActivityEvent",
        "HiringSignalEvent",
        "MACandidateEvent",
        "AcquirerMatchEvent",
        "ReportGeneratedEvent"
      ]
    },
    "event_version": {
      "type": "string",
      "description": "Version of the event schema",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "example": "1.0.0"
    },
    "source": {
      "type": "string",
      "description": "Service/component that produced this event",
      "example": "clinical-trial-signals"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp when event was created",
      "example": "2025-12-07T14:32:15.123Z"
    },
    "correlation_id": {
      "type": "string",
      "description": "Optional ID to correlate related events across services",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    },
    "causation_id": {
      "type": "string",
      "description": "Optional ID of the event that directly caused this event",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    },
    "metadata": {
      "type": "object",
      "description": "Optional metadata for tracking, debugging, or routing",
      "properties": {
        "retry_count": {
          "type": "integer",
          "minimum": 0
        },
        "priority": {
          "type": "string",
          "enum": ["low", "medium", "high", "critical"]
        },
        "tags": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "payload": {
      "type": "object",
      "description": "The actual event data (schema varies by event_type)"
    }
  }
}
```

### Example Envelope

```json
{
  "envelope_version": "1.0.0",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "ClinicalTrialSignalEvent",
  "event_version": "1.0.0",
  "source": "clinical-trial-signals",
  "timestamp": "2025-12-07T14:32:15.123Z",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440111",
  "metadata": {
    "priority": "high",
    "tags": ["phase3", "oncology"]
  },
  "payload": {
    "...": "event-specific data"
  }
}
```

---

## Event Schemas

### ClinicalTrialSignalEvent

Emitted when significant changes occur in clinical trial status, outcomes, or phase progressions.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "company_id",
    "company_name",
    "trial_id",
    "trial_nct_id",
    "drug_name",
    "indication",
    "signal_type",
    "current_phase",
    "signal_date",
    "impact_score"
  ],
  "properties": {
    "company_id": {
      "type": "string",
      "description": "Unique identifier for the company",
      "example": "COMP-12345"
    },
    "company_name": {
      "type": "string",
      "description": "Name of the biotech company",
      "example": "Acme Therapeutics Inc."
    },
    "ticker_symbol": {
      "type": "string",
      "description": "Stock ticker symbol (if publicly traded)",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "trial_id": {
      "type": "string",
      "description": "Internal trial identifier",
      "example": "TRIAL-98765"
    },
    "trial_nct_id": {
      "type": "string",
      "description": "ClinicalTrials.gov NCT identifier",
      "pattern": "^NCT\\d{8}$",
      "example": "NCT04123456"
    },
    "drug_name": {
      "type": "string",
      "description": "Name of the drug/therapeutic being tested",
      "example": "ACM-2001"
    },
    "indication": {
      "type": "string",
      "description": "Medical condition being treated",
      "example": "Non-Small Cell Lung Cancer"
    },
    "therapeutic_area": {
      "type": "string",
      "description": "Broader therapeutic category",
      "enum": [
        "oncology",
        "neurology",
        "cardiovascular",
        "immunology",
        "rare_disease",
        "metabolic",
        "infectious_disease",
        "other"
      ],
      "example": "oncology"
    },
    "signal_type": {
      "type": "string",
      "description": "Type of clinical trial signal detected",
      "enum": [
        "phase_advancement",
        "phase_failure",
        "trial_termination",
        "positive_interim",
        "negative_interim",
        "enrollment_completion",
        "primary_endpoint_met",
        "primary_endpoint_missed",
        "regulatory_breakthrough",
        "fda_fast_track",
        "orphan_designation"
      ],
      "example": "phase_advancement"
    },
    "current_phase": {
      "type": "string",
      "description": "Current trial phase",
      "enum": ["preclinical", "phase1", "phase2", "phase3", "phase4", "post_market"],
      "example": "phase3"
    },
    "previous_phase": {
      "type": "string",
      "description": "Previous trial phase (for phase changes)",
      "enum": ["preclinical", "phase1", "phase2", "phase3", "phase4"],
      "example": "phase2"
    },
    "signal_date": {
      "type": "string",
      "format": "date",
      "description": "Date when the signal was detected",
      "example": "2025-12-01"
    },
    "impact_score": {
      "type": "number",
      "description": "Calculated impact score (0-100) indicating M&A relevance",
      "minimum": 0,
      "maximum": 100,
      "example": 87.5
    },
    "patient_enrollment": {
      "type": "integer",
      "description": "Number of patients enrolled",
      "minimum": 0,
      "example": 450
    },
    "primary_endpoints": {
      "type": "array",
      "description": "Primary endpoints being measured",
      "items": {
        "type": "string"
      },
      "example": ["Overall Survival", "Progression-Free Survival"]
    },
    "trial_status": {
      "type": "string",
      "description": "Current trial status",
      "enum": [
        "recruiting",
        "active_not_recruiting",
        "completed",
        "terminated",
        "suspended",
        "withdrawn"
      ],
      "example": "active_not_recruiting"
    },
    "estimated_completion_date": {
      "type": "string",
      "format": "date",
      "description": "Estimated primary completion date",
      "example": "2026-06-30"
    },
    "data_source": {
      "type": "string",
      "description": "Source of the clinical trial data",
      "example": "ClinicalTrials.gov"
    },
    "url": {
      "type": "string",
      "format": "uri",
      "description": "URL to trial information",
      "example": "https://clinicaltrials.gov/study/NCT04123456"
    },
    "notes": {
      "type": "string",
      "description": "Additional context or observations",
      "maxLength": 1000
    }
  }
}
```

#### Example Payload

```json
{
  "company_id": "COMP-12345",
  "company_name": "Acme Therapeutics Inc.",
  "ticker_symbol": "ACME",
  "trial_id": "TRIAL-98765",
  "trial_nct_id": "NCT04123456",
  "drug_name": "ACM-2001",
  "indication": "Non-Small Cell Lung Cancer",
  "therapeutic_area": "oncology",
  "signal_type": "phase_advancement",
  "current_phase": "phase3",
  "previous_phase": "phase2",
  "signal_date": "2025-12-01",
  "impact_score": 87.5,
  "patient_enrollment": 450,
  "primary_endpoints": [
    "Overall Survival",
    "Progression-Free Survival"
  ],
  "trial_status": "active_not_recruiting",
  "estimated_completion_date": "2026-06-30",
  "data_source": "ClinicalTrials.gov",
  "url": "https://clinicaltrials.gov/study/NCT04123456",
  "notes": "Phase 3 advancement following successful interim analysis showing 40% improvement in PFS"
}
```

---

### PatentCliffEvent

Emitted when patent expirations, generic entry threats, or significant IP landscape changes are detected.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "company_id",
    "company_name",
    "drug_name",
    "patent_number",
    "event_type",
    "expiration_date",
    "threat_level",
    "impact_score"
  ],
  "properties": {
    "company_id": {
      "type": "string",
      "description": "Unique identifier for the company",
      "example": "COMP-12345"
    },
    "company_name": {
      "type": "string",
      "description": "Name of the company holding the patent",
      "example": "Acme Therapeutics Inc."
    },
    "ticker_symbol": {
      "type": "string",
      "description": "Stock ticker symbol (if publicly traded)",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "drug_name": {
      "type": "string",
      "description": "Name of the drug/product protected by patent",
      "example": "ACM-2001"
    },
    "patent_number": {
      "type": "string",
      "description": "Patent number (jurisdiction-specific format)",
      "example": "US10123456B2"
    },
    "patent_title": {
      "type": "string",
      "description": "Title of the patent",
      "example": "Method and composition for treating NSCLC"
    },
    "patent_type": {
      "type": "string",
      "description": "Type of patent protection",
      "enum": [
        "composition_of_matter",
        "method_of_use",
        "formulation",
        "process",
        "combination",
        "other"
      ],
      "example": "composition_of_matter"
    },
    "event_type": {
      "type": "string",
      "description": "Type of patent cliff event",
      "enum": [
        "expiration_imminent",
        "expiration_occurred",
        "generic_challenge",
        "anda_filing",
        "paragraph_iv_certification",
        "patent_invalidation",
        "loss_of_exclusivity",
        "extension_granted",
        "extension_denied"
      ],
      "example": "expiration_imminent"
    },
    "expiration_date": {
      "type": "string",
      "format": "date",
      "description": "Patent expiration date",
      "example": "2026-03-15"
    },
    "filing_date": {
      "type": "string",
      "format": "date",
      "description": "Original patent filing date",
      "example": "2006-03-15"
    },
    "jurisdiction": {
      "type": "string",
      "description": "Jurisdiction where patent is registered",
      "enum": ["US", "EU", "JP", "CN", "CA", "IN", "BR", "OTHER"],
      "example": "US"
    },
    "threat_level": {
      "type": "string",
      "description": "Level of threat to revenue",
      "enum": ["critical", "high", "medium", "low"],
      "example": "critical"
    },
    "impact_score": {
      "type": "number",
      "description": "Calculated impact score (0-100) indicating M&A relevance",
      "minimum": 0,
      "maximum": 100,
      "example": 92.0
    },
    "days_until_expiration": {
      "type": "integer",
      "description": "Number of days until patent expires",
      "minimum": 0,
      "example": 98
    },
    "annual_revenue_at_risk": {
      "type": "number",
      "description": "Estimated annual revenue at risk (USD millions)",
      "minimum": 0,
      "example": 450.5
    },
    "revenue_percentage": {
      "type": "number",
      "description": "Percentage of company revenue from this product",
      "minimum": 0,
      "maximum": 100,
      "example": 67.5
    },
    "generic_competitors": {
      "type": "array",
      "description": "Known generic competitors or ANDA filers",
      "items": {
        "type": "object",
        "properties": {
          "company_name": {
            "type": "string"
          },
          "filing_date": {
            "type": "string",
            "format": "date"
          },
          "status": {
            "type": "string"
          }
        }
      }
    },
    "exclusivity_extensions": {
      "type": "array",
      "description": "Any exclusivity extensions (pediatric, orphan, etc.)",
      "items": {
        "type": "object",
        "properties": {
          "extension_type": {
            "type": "string"
          },
          "extension_date": {
            "type": "string",
            "format": "date"
          },
          "additional_months": {
            "type": "integer"
          }
        }
      }
    },
    "related_patents": {
      "type": "array",
      "description": "Related patent numbers in the patent family",
      "items": {
        "type": "string"
      },
      "example": ["US10987654B2", "EP2345678A1"]
    },
    "data_source": {
      "type": "string",
      "description": "Source of patent information",
      "example": "USPTO, Orange Book"
    },
    "url": {
      "type": "string",
      "format": "uri",
      "description": "URL to patent details",
      "example": "https://patents.google.com/patent/US10123456B2"
    },
    "notes": {
      "type": "string",
      "description": "Additional context or observations",
      "maxLength": 1000
    }
  }
}
```

#### Example Payload

```json
{
  "company_id": "COMP-12345",
  "company_name": "Acme Therapeutics Inc.",
  "ticker_symbol": "ACME",
  "drug_name": "ACM-2001",
  "patent_number": "US10123456B2",
  "patent_title": "Method and composition for treating NSCLC",
  "patent_type": "composition_of_matter",
  "event_type": "expiration_imminent",
  "expiration_date": "2026-03-15",
  "filing_date": "2006-03-15",
  "jurisdiction": "US",
  "threat_level": "critical",
  "impact_score": 92.0,
  "days_until_expiration": 98,
  "annual_revenue_at_risk": 450.5,
  "revenue_percentage": 67.5,
  "generic_competitors": [
    {
      "company_name": "Generic Pharma Corp",
      "filing_date": "2025-09-15",
      "status": "Paragraph IV certification filed"
    }
  ],
  "exclusivity_extensions": [],
  "related_patents": ["US10987654B2", "EP2345678A1"],
  "data_source": "USPTO, Orange Book",
  "url": "https://patents.google.com/patent/US10123456B2",
  "notes": "Critical revenue driver with no pipeline replacement. High M&A vulnerability."
}
```

---

### InsiderActivityEvent

Emitted when significant insider trading activity or institutional investor movements are detected via Form 4 or 13F filings.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "company_id",
    "company_name",
    "activity_type",
    "filing_type",
    "filing_date",
    "transaction_date",
    "impact_score"
  ],
  "properties": {
    "company_id": {
      "type": "string",
      "description": "Unique identifier for the company",
      "example": "COMP-12345"
    },
    "company_name": {
      "type": "string",
      "description": "Name of the company",
      "example": "Acme Therapeutics Inc."
    },
    "ticker_symbol": {
      "type": "string",
      "description": "Stock ticker symbol",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "activity_type": {
      "type": "string",
      "description": "Type of insider activity",
      "enum": [
        "insider_buy",
        "insider_sell",
        "institutional_buy",
        "institutional_sell",
        "institutional_new_position",
        "institutional_exit",
        "option_exercise",
        "stock_award"
      ],
      "example": "insider_buy"
    },
    "filing_type": {
      "type": "string",
      "description": "SEC filing type",
      "enum": ["form_4", "form_13f", "form_13d", "form_13g"],
      "example": "form_4"
    },
    "filing_date": {
      "type": "string",
      "format": "date",
      "description": "Date when filing was submitted to SEC",
      "example": "2025-12-05"
    },
    "transaction_date": {
      "type": "string",
      "format": "date",
      "description": "Date when transaction occurred",
      "example": "2025-12-03"
    },
    "insider_name": {
      "type": "string",
      "description": "Name of the insider (for Form 4)",
      "example": "John Smith"
    },
    "insider_title": {
      "type": "string",
      "description": "Title/role of the insider",
      "example": "Chief Executive Officer"
    },
    "insider_relationship": {
      "type": "string",
      "description": "Relationship to company",
      "enum": [
        "director",
        "ceo",
        "cfo",
        "coo",
        "cto",
        "chief_medical_officer",
        "chief_scientific_officer",
        "vp",
        "officer",
        "ten_percent_owner",
        "other"
      ],
      "example": "ceo"
    },
    "institutional_investor": {
      "type": "string",
      "description": "Name of institutional investor (for Form 13F)",
      "example": "Vanguard Group Inc."
    },
    "investor_type": {
      "type": "string",
      "description": "Type of institutional investor",
      "enum": [
        "hedge_fund",
        "mutual_fund",
        "pension_fund",
        "venture_capital",
        "private_equity",
        "family_office",
        "sovereign_wealth",
        "other"
      ],
      "example": "hedge_fund"
    },
    "transaction_code": {
      "type": "string",
      "description": "SEC transaction code",
      "enum": ["P", "S", "A", "D", "F", "M", "G", "C", "I", "J", "K", "L", "W", "X"],
      "example": "P"
    },
    "shares_transacted": {
      "type": "integer",
      "description": "Number of shares bought/sold",
      "minimum": 0,
      "example": 50000
    },
    "price_per_share": {
      "type": "number",
      "description": "Price per share (USD)",
      "minimum": 0,
      "example": 45.50
    },
    "total_value": {
      "type": "number",
      "description": "Total transaction value (USD)",
      "minimum": 0,
      "example": 2275000
    },
    "shares_owned_after": {
      "type": "integer",
      "description": "Total shares owned after transaction",
      "minimum": 0,
      "example": 250000
    },
    "ownership_percentage": {
      "type": "number",
      "description": "Percentage ownership after transaction",
      "minimum": 0,
      "maximum": 100,
      "example": 2.5
    },
    "ownership_change_percentage": {
      "type": "number",
      "description": "Change in ownership percentage",
      "example": 0.5
    },
    "is_derivative": {
      "type": "boolean",
      "description": "Whether transaction involves derivative securities",
      "example": false
    },
    "impact_score": {
      "type": "number",
      "description": "Calculated impact score (0-100) indicating M&A signal strength",
      "minimum": 0,
      "maximum": 100,
      "example": 75.0
    },
    "signal_strength": {
      "type": "string",
      "description": "Signal strength interpretation",
      "enum": ["strong_buy_signal", "moderate_buy_signal", "neutral", "moderate_sell_signal", "strong_sell_signal"],
      "example": "strong_buy_signal"
    },
    "filing_url": {
      "type": "string",
      "format": "uri",
      "description": "URL to SEC filing",
      "example": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001234567"
    },
    "notes": {
      "type": "string",
      "description": "Additional context or observations",
      "maxLength": 1000
    }
  }
}
```

#### Example Payload

```json
{
  "company_id": "COMP-12345",
  "company_name": "Acme Therapeutics Inc.",
  "ticker_symbol": "ACME",
  "activity_type": "insider_buy",
  "filing_type": "form_4",
  "filing_date": "2025-12-05",
  "transaction_date": "2025-12-03",
  "insider_name": "John Smith",
  "insider_title": "Chief Executive Officer",
  "insider_relationship": "ceo",
  "transaction_code": "P",
  "shares_transacted": 50000,
  "price_per_share": 45.50,
  "total_value": 2275000,
  "shares_owned_after": 250000,
  "ownership_percentage": 2.5,
  "ownership_change_percentage": 0.5,
  "is_derivative": false,
  "impact_score": 75.0,
  "signal_strength": "strong_buy_signal",
  "filing_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001234567",
  "notes": "CEO significant open market purchase following patent cliff announcement. Potential confidence signal."
}
```

---

### HiringSignalEvent

Emitted when key executive or scientific talent movements are detected through job postings, LinkedIn, or other sources.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "company_id",
    "company_name",
    "signal_type",
    "role_title",
    "signal_date",
    "impact_score"
  ],
  "properties": {
    "company_id": {
      "type": "string",
      "description": "Unique identifier for the company",
      "example": "COMP-12345"
    },
    "company_name": {
      "type": "string",
      "description": "Name of the company",
      "example": "Acme Therapeutics Inc."
    },
    "ticker_symbol": {
      "type": "string",
      "description": "Stock ticker symbol (if publicly traded)",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "signal_type": {
      "type": "string",
      "description": "Type of hiring signal",
      "enum": [
        "executive_hire",
        "executive_departure",
        "scientist_hire",
        "scientist_departure",
        "mass_hiring",
        "hiring_freeze",
        "layoff_announced",
        "job_posting_surge",
        "c_suite_turnover"
      ],
      "example": "executive_hire"
    },
    "role_title": {
      "type": "string",
      "description": "Job title or role",
      "example": "Chief Business Development Officer"
    },
    "role_category": {
      "type": "string",
      "description": "Category of role",
      "enum": [
        "c_suite",
        "vp_level",
        "director_level",
        "principal_scientist",
        "senior_scientist",
        "business_development",
        "regulatory_affairs",
        "clinical_operations",
        "manufacturing",
        "other"
      ],
      "example": "c_suite"
    },
    "person_name": {
      "type": "string",
      "description": "Name of person hired/departed (if known)",
      "example": "Jane Doe"
    },
    "previous_company": {
      "type": "string",
      "description": "Previous company (for hires)",
      "example": "Big Pharma Corp"
    },
    "previous_role": {
      "type": "string",
      "description": "Previous role title",
      "example": "VP of Corporate Development"
    },
    "destination_company": {
      "type": "string",
      "description": "Destination company (for departures)",
      "example": "Competitor Biotech Inc."
    },
    "signal_date": {
      "type": "string",
      "format": "date",
      "description": "Date when signal was detected",
      "example": "2025-12-04"
    },
    "effective_date": {
      "type": "string",
      "format": "date",
      "description": "Effective date of hire/departure",
      "example": "2025-12-15"
    },
    "department": {
      "type": "string",
      "description": "Department or functional area",
      "example": "Business Development"
    },
    "location": {
      "type": "string",
      "description": "Job location",
      "example": "Boston, MA"
    },
    "remote_status": {
      "type": "string",
      "enum": ["on_site", "hybrid", "remote"],
      "example": "hybrid"
    },
    "number_of_positions": {
      "type": "integer",
      "description": "Number of open positions (for mass hiring signals)",
      "minimum": 1,
      "example": 1
    },
    "expertise_areas": {
      "type": "array",
      "description": "Areas of expertise relevant to the role",
      "items": {
        "type": "string"
      },
      "example": ["M&A", "Licensing", "Strategic Partnerships"]
    },
    "impact_score": {
      "type": "number",
      "description": "Calculated impact score (0-100) indicating M&A signal strength",
      "minimum": 0,
      "maximum": 100,
      "example": 82.0
    },
    "signal_interpretation": {
      "type": "string",
      "description": "Interpretation of what this signal may indicate",
      "enum": [
        "preparing_for_acquisition",
        "growth_mode",
        "restructuring",
        "financial_distress",
        "strategic_pivot",
        "normal_turnover",
        "expansion"
      ],
      "example": "preparing_for_acquisition"
    },
    "data_source": {
      "type": "string",
      "description": "Source of the hiring information",
      "example": "LinkedIn Jobs, Company Press Release"
    },
    "source_url": {
      "type": "string",
      "format": "uri",
      "description": "URL to source information",
      "example": "https://www.linkedin.com/jobs/view/1234567890"
    },
    "notes": {
      "type": "string",
      "description": "Additional context or observations",
      "maxLength": 1000
    }
  }
}
```

#### Example Payload

```json
{
  "company_id": "COMP-12345",
  "company_name": "Acme Therapeutics Inc.",
  "ticker_symbol": "ACME",
  "signal_type": "executive_hire",
  "role_title": "Chief Business Development Officer",
  "role_category": "c_suite",
  "person_name": "Jane Doe",
  "previous_company": "Big Pharma Corp",
  "previous_role": "VP of Corporate Development",
  "signal_date": "2025-12-04",
  "effective_date": "2025-12-15",
  "department": "Business Development",
  "location": "Boston, MA",
  "remote_status": "hybrid",
  "number_of_positions": 1,
  "expertise_areas": ["M&A", "Licensing", "Strategic Partnerships"],
  "impact_score": 82.0,
  "signal_interpretation": "preparing_for_acquisition",
  "data_source": "LinkedIn Jobs, Company Press Release",
  "source_url": "https://www.linkedin.com/jobs/view/1234567890",
  "notes": "New CBDO with strong M&A background from major pharma. Potential signal of sale preparation."
}
```

---

### MACandidateEvent

Emitted when a company is flagged as a potential M&A acquisition target based on aggregated signals.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "candidate_id",
    "company_id",
    "company_name",
    "ma_probability_score",
    "confidence_level",
    "signal_summary",
    "evaluation_date"
  ],
  "properties": {
    "candidate_id": {
      "type": "string",
      "description": "Unique identifier for this M&A candidate assessment",
      "example": "CAND-2025-001"
    },
    "company_id": {
      "type": "string",
      "description": "Unique identifier for the company",
      "example": "COMP-12345"
    },
    "company_name": {
      "type": "string",
      "description": "Name of the candidate company",
      "example": "Acme Therapeutics Inc."
    },
    "ticker_symbol": {
      "type": "string",
      "description": "Stock ticker symbol (if publicly traded)",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "ma_probability_score": {
      "type": "number",
      "description": "Calculated probability score (0-100) that company will be acquired",
      "minimum": 0,
      "maximum": 100,
      "example": 87.5
    },
    "confidence_level": {
      "type": "string",
      "description": "Confidence level in the prediction",
      "enum": ["very_high", "high", "medium", "low"],
      "example": "high"
    },
    "evaluation_date": {
      "type": "string",
      "format": "date",
      "description": "Date when evaluation was performed",
      "example": "2025-12-07"
    },
    "signal_summary": {
      "type": "object",
      "description": "Summary of contributing signals",
      "required": ["clinical_signals", "patent_signals", "insider_signals", "hiring_signals"],
      "properties": {
        "clinical_signals": {
          "type": "object",
          "properties": {
            "count": {
              "type": "integer",
              "minimum": 0
            },
            "average_impact": {
              "type": "number",
              "minimum": 0,
              "maximum": 100
            },
            "key_events": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        },
        "patent_signals": {
          "type": "object",
          "properties": {
            "count": {
              "type": "integer",
              "minimum": 0
            },
            "average_impact": {
              "type": "number",
              "minimum": 0,
              "maximum": 100
            },
            "key_events": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        },
        "insider_signals": {
          "type": "object",
          "properties": {
            "count": {
              "type": "integer",
              "minimum": 0
            },
            "average_impact": {
              "type": "number",
              "minimum": 0,
              "maximum": 100
            },
            "key_events": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        },
        "hiring_signals": {
          "type": "object",
          "properties": {
            "count": {
              "type": "integer",
              "minimum": 0
            },
            "average_impact": {
              "type": "number",
              "minimum": 0,
              "maximum": 100
            },
            "key_events": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        }
      }
    },
    "contributing_event_ids": {
      "type": "array",
      "description": "Event IDs that contributed to this M&A candidate assessment",
      "items": {
        "type": "string",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
      },
      "example": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440111"
      ]
    },
    "primary_drivers": {
      "type": "array",
      "description": "Primary factors driving M&A likelihood",
      "items": {
        "type": "string",
        "enum": [
          "patent_cliff",
          "clinical_success",
          "clinical_failure",
          "cash_burn",
          "insider_buying",
          "leadership_changes",
          "strategic_hiring",
          "market_conditions",
          "competitive_pressure",
          "regulatory_pressure"
        ]
      },
      "example": ["patent_cliff", "strategic_hiring"]
    },
    "company_financials": {
      "type": "object",
      "description": "Key financial metrics",
      "properties": {
        "market_cap_usd": {
          "type": "number",
          "description": "Market capitalization in USD millions",
          "example": 450.5
        },
        "cash_position_usd": {
          "type": "number",
          "description": "Cash and equivalents in USD millions",
          "example": 85.2
        },
        "quarterly_burn_rate_usd": {
          "type": "number",
          "description": "Quarterly cash burn in USD millions",
          "example": 22.5
        },
        "runway_months": {
          "type": "integer",
          "description": "Estimated cash runway in months",
          "example": 15
        },
        "debt_usd": {
          "type": "number",
          "description": "Total debt in USD millions",
          "example": 50.0
        }
      }
    },
    "pipeline_overview": {
      "type": "object",
      "description": "Summary of drug pipeline",
      "properties": {
        "total_assets": {
          "type": "integer",
          "minimum": 0,
          "example": 5
        },
        "phase3_assets": {
          "type": "integer",
          "minimum": 0,
          "example": 1
        },
        "phase2_assets": {
          "type": "integer",
          "minimum": 0,
          "example": 2
        },
        "phase1_assets": {
          "type": "integer",
          "minimum": 0,
          "example": 2
        },
        "lead_asset": {
          "type": "string",
          "example": "ACM-2001"
        },
        "lead_indication": {
          "type": "string",
          "example": "Non-Small Cell Lung Cancer"
        }
      }
    },
    "therapeutic_focus": {
      "type": "array",
      "description": "Primary therapeutic areas",
      "items": {
        "type": "string"
      },
      "example": ["oncology", "immunology"]
    },
    "technology_platform": {
      "type": "array",
      "description": "Core technology platforms",
      "items": {
        "type": "string"
      },
      "example": ["small molecule", "antibody-drug conjugate"]
    },
    "estimated_valuation_range": {
      "type": "object",
      "description": "Estimated acquisition valuation range",
      "properties": {
        "low_usd": {
          "type": "number",
          "description": "Low estimate in USD millions",
          "example": 800
        },
        "high_usd": {
          "type": "number",
          "description": "High estimate in USD millions",
          "example": 1500
        },
        "basis": {
          "type": "string",
          "description": "Basis for valuation estimate",
          "example": "Comparable transactions, DCF analysis"
        }
      }
    },
    "timeline_estimate": {
      "type": "object",
      "description": "Estimated timeline for potential acquisition",
      "properties": {
        "earliest_date": {
          "type": "string",
          "format": "date",
          "example": "2026-03-01"
        },
        "most_likely_date": {
          "type": "string",
          "format": "date",
          "example": "2026-06-30"
        },
        "latest_date": {
          "type": "string",
          "format": "date",
          "example": "2026-12-31"
        }
      }
    },
    "risk_factors": {
      "type": "array",
      "description": "Key risk factors that could prevent acquisition",
      "items": {
        "type": "string"
      },
      "example": [
        "Clinical trial failure risk",
        "High valuation expectations",
        "Competitive bidding scenario"
      ]
    },
    "notes": {
      "type": "string",
      "description": "Additional analysis and context",
      "maxLength": 2000
    }
  }
}
```

#### Example Payload

```json
{
  "candidate_id": "CAND-2025-001",
  "company_id": "COMP-12345",
  "company_name": "Acme Therapeutics Inc.",
  "ticker_symbol": "ACME",
  "ma_probability_score": 87.5,
  "confidence_level": "high",
  "evaluation_date": "2025-12-07",
  "signal_summary": {
    "clinical_signals": {
      "count": 3,
      "average_impact": 85.0,
      "key_events": [
        "Phase 3 advancement for ACM-2001",
        "Positive interim analysis"
      ]
    },
    "patent_signals": {
      "count": 2,
      "average_impact": 92.0,
      "key_events": [
        "Primary patent expiring Q1 2026",
        "67.5% revenue at risk"
      ]
    },
    "insider_signals": {
      "count": 1,
      "average_impact": 75.0,
      "key_events": [
        "CEO significant open market purchase"
      ]
    },
    "hiring_signals": {
      "count": 1,
      "average_impact": 82.0,
      "key_events": [
        "New CBDO with M&A background hired"
      ]
    }
  },
  "contributing_event_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440111",
    "770e8400-e29b-41d4-a716-446655440222",
    "880e8400-e29b-41d4-a716-446655440333"
  ],
  "primary_drivers": ["patent_cliff", "strategic_hiring"],
  "company_financials": {
    "market_cap_usd": 450.5,
    "cash_position_usd": 85.2,
    "quarterly_burn_rate_usd": 22.5,
    "runway_months": 15,
    "debt_usd": 50.0
  },
  "pipeline_overview": {
    "total_assets": 5,
    "phase3_assets": 1,
    "phase2_assets": 2,
    "phase1_assets": 2,
    "lead_asset": "ACM-2001",
    "lead_indication": "Non-Small Cell Lung Cancer"
  },
  "therapeutic_focus": ["oncology", "immunology"],
  "technology_platform": ["small molecule", "antibody-drug conjugate"],
  "estimated_valuation_range": {
    "low_usd": 800,
    "high_usd": 1500,
    "basis": "Comparable transactions, DCF analysis"
  },
  "timeline_estimate": {
    "earliest_date": "2026-03-01",
    "most_likely_date": "2026-06-30",
    "latest_date": "2026-12-31"
  },
  "risk_factors": [
    "Clinical trial failure risk",
    "High valuation expectations",
    "Competitive bidding scenario"
  ],
  "notes": "Strong M&A candidate driven by imminent patent cliff and strategic positioning moves. Company appears to be preparing for sale with key BD hire. Phase 3 asset provides compelling acquisition rationale for larger pharma seeking oncology portfolio expansion."
}
```

---

### AcquirerMatchEvent

Emitted when a potential acquirer-target pairing is identified based on strategic fit, therapeutic alignment, and historical patterns.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "match_id",
    "target_company_id",
    "target_company_name",
    "acquirer_company_id",
    "acquirer_company_name",
    "match_score",
    "strategic_rationale",
    "evaluation_date"
  ],
  "properties": {
    "match_id": {
      "type": "string",
      "description": "Unique identifier for this match",
      "example": "MATCH-2025-001"
    },
    "target_company_id": {
      "type": "string",
      "description": "Identifier for the acquisition target",
      "example": "COMP-12345"
    },
    "target_company_name": {
      "type": "string",
      "description": "Name of the target company",
      "example": "Acme Therapeutics Inc."
    },
    "target_ticker_symbol": {
      "type": "string",
      "description": "Target stock ticker symbol",
      "pattern": "^[A-Z]{1,5}$",
      "example": "ACME"
    },
    "acquirer_company_id": {
      "type": "string",
      "description": "Identifier for the potential acquirer",
      "example": "COMP-67890"
    },
    "acquirer_company_name": {
      "type": "string",
      "description": "Name of the potential acquirer",
      "example": "Global Pharma Corporation"
    },
    "acquirer_ticker_symbol": {
      "type": "string",
      "description": "Acquirer stock ticker symbol",
      "pattern": "^[A-Z]{1,5}$",
      "example": "GPC"
    },
    "match_score": {
      "type": "number",
      "description": "Overall match quality score (0-100)",
      "minimum": 0,
      "maximum": 100,
      "example": 89.5
    },
    "evaluation_date": {
      "type": "string",
      "format": "date",
      "description": "Date when match evaluation was performed",
      "example": "2025-12-07"
    },
    "strategic_rationale": {
      "type": "object",
      "description": "Strategic reasons for the match",
      "required": ["primary_rationale", "supporting_factors"],
      "properties": {
        "primary_rationale": {
          "type": "string",
          "description": "Main strategic driver",
          "enum": [
            "pipeline_gap_fill",
            "therapeutic_area_expansion",
            "technology_acquisition",
            "geographic_expansion",
            "defensive_acquisition",
            "talent_acquisition",
            "portfolio_diversification",
            "manufacturing_capacity",
            "market_share_consolidation"
          ],
          "example": "pipeline_gap_fill"
        },
        "supporting_factors": {
          "type": "array",
          "description": "Additional supporting factors",
          "items": {
            "type": "string"
          },
          "example": [
            "Therapeutic area alignment",
            "Phase 3 asset de-risks acquisition",
            "Historical acquisition pattern match"
          ]
        }
      }
    },
    "therapeutic_alignment": {
      "type": "object",
      "description": "Therapeutic area fit analysis",
      "properties": {
        "alignment_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "example": 95.0
        },
        "overlapping_areas": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "example": ["oncology"]
        },
        "complementary_areas": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "example": ["immunology"]
        },
        "acquirer_gaps": {
          "type": "array",
          "description": "Therapeutic gaps this acquisition would fill",
          "items": {
            "type": "string"
          },
          "example": ["NSCLC pipeline gap in late-stage"]
        }
      }
    },
    "technology_fit": {
      "type": "object",
      "description": "Technology platform alignment",
      "properties": {
        "fit_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "example": 85.0
        },
        "platform_overlap": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "example": ["small molecule"]
        },
        "platform_expansion": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "example": ["antibody-drug conjugate"]
        }
      }
    },
    "financial_fit": {
      "type": "object",
      "description": "Financial compatibility analysis",
      "properties": {
        "fit_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "example": 90.0
        },
        "target_valuation_usd": {
          "type": "number",
          "description": "Estimated target valuation in USD millions",
          "example": 1200
        },
        "acquirer_market_cap_usd": {
          "type": "number",
          "description": "Acquirer market cap in USD millions",
          "example": 45000
        },
        "deal_size_percentage": {
          "type": "number",
          "description": "Deal size as percentage of acquirer market cap",
          "example": 2.67
        },
        "acquirer_cash_position_usd": {
          "type": "number",
          "description": "Acquirer cash position in USD millions",
          "example": 8500
        },
        "financing_feasibility": {
          "type": "string",
          "enum": ["highly_feasible", "feasible", "challenging", "unlikely"],
          "example": "highly_feasible"
        }
      }
    },
    "historical_precedent": {
      "type": "object",
      "description": "Historical acquisition pattern analysis",
      "properties": {
        "precedent_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "example": 78.0
        },
        "acquirer_deal_history": {
          "type": "object",
          "properties": {
            "total_deals_5y": {
              "type": "integer",
              "example": 12
            },
            "average_deal_size_usd": {
              "type": "number",
              "example": 1500
            },
            "preferred_stages": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "example": ["phase2", "phase3"]
            },
            "preferred_therapeutics": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "example": ["oncology", "rare_disease"]
            }
          }
        },
        "comparable_deals": {
          "type": "array",
          "description": "Similar historical transactions",
          "items": {
            "type": "object",
            "properties": {
              "date": {
                "type": "string",
                "format": "date"
              },
              "target": {
                "type": "string"
              },
              "acquirer": {
                "type": "string"
              },
              "value_usd": {
                "type": "number"
              },
              "similarity_score": {
                "type": "number"
              }
            }
          }
        }
      }
    },
    "synergies": {
      "type": "array",
      "description": "Identified potential synergies",
      "items": {
        "type": "object",
        "properties": {
          "synergy_type": {
            "type": "string",
            "enum": [
              "revenue_synergy",
              "cost_synergy",
              "rd_synergy",
              "commercial_synergy",
              "manufacturing_synergy",
              "regulatory_synergy"
            ]
          },
          "description": {
            "type": "string"
          },
          "estimated_value_usd": {
            "type": "number"
          }
        }
      }
    },
    "risks": {
      "type": "array",
      "description": "Key risks to deal completion",
      "items": {
        "type": "object",
        "properties": {
          "risk_type": {
            "type": "string",
            "enum": [
              "regulatory_risk",
              "antitrust_risk",
              "integration_risk",
              "clinical_risk",
              "valuation_risk",
              "competitive_bid_risk",
              "financing_risk"
            ]
          },
          "description": {
            "type": "string"
          },
          "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"]
          }
        }
      }
    },
    "probability_estimate": {
      "type": "number",
      "description": "Estimated probability (0-100) of deal occurring within 18 months",
      "minimum": 0,
      "maximum": 100,
      "example": 45.0
    },
    "timeline_estimate": {
      "type": "object",
      "description": "Estimated deal timeline",
      "properties": {
        "earliest_announcement": {
          "type": "string",
          "format": "date",
          "example": "2026-01-01"
        },
        "most_likely_announcement": {
          "type": "string",
          "format": "date",
          "example": "2026-04-15"
        },
        "latest_announcement": {
          "type": "string",
          "format": "date",
          "example": "2026-09-30"
        }
      }
    },
    "confidence_level": {
      "type": "string",
      "description": "Confidence in the match prediction",
      "enum": ["very_high", "high", "medium", "low"],
      "example": "high"
    },
    "ma_candidate_event_id": {
      "type": "string",
      "description": "Reference to the MACandidateEvent that triggered this match",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    },
    "notes": {
      "type": "string",
      "description": "Additional analysis and context",
      "maxLength": 2000
    }
  }
}
```

#### Example Payload

```json
{
  "match_id": "MATCH-2025-001",
  "target_company_id": "COMP-12345",
  "target_company_name": "Acme Therapeutics Inc.",
  "target_ticker_symbol": "ACME",
  "acquirer_company_id": "COMP-67890",
  "acquirer_company_name": "Global Pharma Corporation",
  "acquirer_ticker_symbol": "GPC",
  "match_score": 89.5,
  "evaluation_date": "2025-12-07",
  "strategic_rationale": {
    "primary_rationale": "pipeline_gap_fill",
    "supporting_factors": [
      "Therapeutic area alignment",
      "Phase 3 asset de-risks acquisition",
      "Historical acquisition pattern match"
    ]
  },
  "therapeutic_alignment": {
    "alignment_score": 95.0,
    "overlapping_areas": ["oncology"],
    "complementary_areas": ["immunology"],
    "acquirer_gaps": ["NSCLC pipeline gap in late-stage"]
  },
  "technology_fit": {
    "fit_score": 85.0,
    "platform_overlap": ["small molecule"],
    "platform_expansion": ["antibody-drug conjugate"]
  },
  "financial_fit": {
    "fit_score": 90.0,
    "target_valuation_usd": 1200,
    "acquirer_market_cap_usd": 45000,
    "deal_size_percentage": 2.67,
    "acquirer_cash_position_usd": 8500,
    "financing_feasibility": "highly_feasible"
  },
  "historical_precedent": {
    "precedent_score": 78.0,
    "acquirer_deal_history": {
      "total_deals_5y": 12,
      "average_deal_size_usd": 1500,
      "preferred_stages": ["phase2", "phase3"],
      "preferred_therapeutics": ["oncology", "rare_disease"]
    },
    "comparable_deals": [
      {
        "date": "2024-06-15",
        "target": "Similar Biotech Corp",
        "acquirer": "Global Pharma Corporation",
        "value_usd": 1400,
        "similarity_score": 85.0
      }
    ]
  },
  "synergies": [
    {
      "synergy_type": "revenue_synergy",
      "description": "Leverage GPC's global commercial infrastructure for ACM-2001 launch",
      "estimated_value_usd": 500
    },
    {
      "synergy_type": "rd_synergy",
      "description": "Combine ADC platform with GPC's biologics expertise",
      "estimated_value_usd": 200
    }
  ],
  "risks": [
    {
      "risk_type": "clinical_risk",
      "description": "Phase 3 trial completion required before deal closure",
      "severity": "medium"
    },
    {
      "risk_type": "competitive_bid_risk",
      "description": "Multiple pharma companies may compete for asset",
      "severity": "medium"
    }
  ],
  "probability_estimate": 45.0,
  "timeline_estimate": {
    "earliest_announcement": "2026-01-01",
    "most_likely_announcement": "2026-04-15",
    "latest_announcement": "2026-09-30"
  },
  "confidence_level": "high",
  "ma_candidate_event_id": "880e8400-e29b-41d4-a716-446655440333",
  "notes": "Strong strategic fit with GPC's oncology portfolio expansion strategy. Target's Phase 3 NSCLC asset addresses known pipeline gap. Patent cliff situation may accelerate seller timeline. Historical pattern suggests GPC comfort with this deal size and stage."
}
```

---

### ReportGeneratedEvent

Emitted when M&A analysis reports are generated for distribution to stakeholders.

#### Schema Version: 1.0.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "report_id",
    "report_type",
    "report_title",
    "generation_date",
    "reporting_period",
    "output_format"
  ],
  "properties": {
    "report_id": {
      "type": "string",
      "description": "Unique identifier for the report",
      "example": "RPT-2025-12-001"
    },
    "report_type": {
      "type": "string",
      "description": "Type of report generated",
      "enum": [
        "daily_signal_digest",
        "weekly_candidate_summary",
        "monthly_market_analysis",
        "candidate_deep_dive",
        "acquirer_match_report",
        "sector_analysis",
        "alert_report",
        "executive_summary"
      ],
      "example": "weekly_candidate_summary"
    },
    "report_title": {
      "type": "string",
      "description": "Title of the report",
      "example": "Weekly M&A Candidate Summary - December 2025 Week 1"
    },
    "generation_date": {
      "type": "string",
      "format": "date-time",
      "description": "Date and time when report was generated",
      "example": "2025-12-07T18:30:00.000Z"
    },
    "reporting_period": {
      "type": "object",
      "description": "Time period covered by the report",
      "required": ["start_date", "end_date"],
      "properties": {
        "start_date": {
          "type": "string",
          "format": "date",
          "example": "2025-12-01"
        },
        "end_date": {
          "type": "string",
          "format": "date",
          "example": "2025-12-07"
        }
      }
    },
    "output_format": {
      "type": "array",
      "description": "Output formats generated",
      "items": {
        "type": "string",
        "enum": ["pdf", "html", "json", "xlsx", "markdown"]
      },
      "example": ["pdf", "html"]
    },
    "report_sections": {
      "type": "array",
      "description": "Sections included in the report",
      "items": {
        "type": "string",
        "enum": [
          "executive_summary",
          "new_candidates",
          "updated_candidates",
          "acquirer_matches",
          "signal_analysis",
          "market_trends",
          "risk_factors",
          "recommendations",
          "appendix"
        ]
      },
      "example": [
        "executive_summary",
        "new_candidates",
        "acquirer_matches"
      ]
    },
    "summary_statistics": {
      "type": "object",
      "description": "Key statistics from the report",
      "properties": {
        "total_candidates": {
          "type": "integer",
          "minimum": 0,
          "example": 12
        },
        "new_candidates": {
          "type": "integer",
          "minimum": 0,
          "example": 3
        },
        "high_probability_candidates": {
          "type": "integer",
          "minimum": 0,
          "example": 5
        },
        "total_matches": {
          "type": "integer",
          "minimum": 0,
          "example": 28
        },
        "new_signals": {
          "type": "integer",
          "minimum": 0,
          "example": 47
        },
        "clinical_signals": {
          "type": "integer",
          "minimum": 0,
          "example": 18
        },
        "patent_signals": {
          "type": "integer",
          "minimum": 0,
          "example": 8
        },
        "insider_signals": {
          "type": "integer",
          "minimum": 0,
          "example": 12
        },
        "hiring_signals": {
          "type": "integer",
          "minimum": 0,
          "example": 9
        }
      }
    },
    "featured_candidates": {
      "type": "array",
      "description": "Top M&A candidates featured in this report",
      "items": {
        "type": "object",
        "properties": {
          "company_id": {
            "type": "string"
          },
          "company_name": {
            "type": "string"
          },
          "ma_probability_score": {
            "type": "number"
          },
          "rank": {
            "type": "integer"
          }
        }
      }
    },
    "featured_matches": {
      "type": "array",
      "description": "Top acquirer-target matches featured in this report",
      "items": {
        "type": "object",
        "properties": {
          "match_id": {
            "type": "string"
          },
          "target_name": {
            "type": "string"
          },
          "acquirer_name": {
            "type": "string"
          },
          "match_score": {
            "type": "number"
          },
          "rank": {
            "type": "integer"
          }
        }
      }
    },
    "distribution_list": {
      "type": "array",
      "description": "Recipients of the report",
      "items": {
        "type": "object",
        "properties": {
          "recipient_id": {
            "type": "string"
          },
          "recipient_name": {
            "type": "string"
          },
          "recipient_email": {
            "type": "string",
            "format": "email"
          },
          "delivery_method": {
            "type": "string",
            "enum": ["email", "portal", "api", "sftp"]
          }
        }
      }
    },
    "file_locations": {
      "type": "array",
      "description": "Storage locations for generated report files",
      "items": {
        "type": "object",
        "properties": {
          "format": {
            "type": "string"
          },
          "path": {
            "type": "string"
          },
          "size_bytes": {
            "type": "integer"
          },
          "url": {
            "type": "string",
            "format": "uri"
          }
        }
      }
    },
    "generation_metadata": {
      "type": "object",
      "description": "Metadata about report generation",
      "properties": {
        "generation_duration_ms": {
          "type": "integer",
          "description": "Time taken to generate report in milliseconds",
          "example": 3456
        },
        "template_version": {
          "type": "string",
          "example": "2.1.0"
        },
        "data_sources": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "example": [
            "clinical-trial-signals",
            "patent-ip-intelligence",
            "insider-hiring-signals"
          ]
        },
        "data_freshness": {
          "type": "string",
          "format": "date-time",
          "description": "Timestamp of most recent data used in report",
          "example": "2025-12-07T17:45:00.000Z"
        }
      }
    },
    "related_event_ids": {
      "type": "array",
      "description": "Event IDs referenced in this report",
      "items": {
        "type": "string",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
      }
    },
    "notes": {
      "type": "string",
      "description": "Additional notes about report generation",
      "maxLength": 1000
    }
  }
}
```

#### Example Payload

```json
{
  "report_id": "RPT-2025-12-001",
  "report_type": "weekly_candidate_summary",
  "report_title": "Weekly M&A Candidate Summary - December 2025 Week 1",
  "generation_date": "2025-12-07T18:30:00.000Z",
  "reporting_period": {
    "start_date": "2025-12-01",
    "end_date": "2025-12-07"
  },
  "output_format": ["pdf", "html"],
  "report_sections": [
    "executive_summary",
    "new_candidates",
    "acquirer_matches",
    "signal_analysis"
  ],
  "summary_statistics": {
    "total_candidates": 12,
    "new_candidates": 3,
    "high_probability_candidates": 5,
    "total_matches": 28,
    "new_signals": 47,
    "clinical_signals": 18,
    "patent_signals": 8,
    "insider_signals": 12,
    "hiring_signals": 9
  },
  "featured_candidates": [
    {
      "company_id": "COMP-12345",
      "company_name": "Acme Therapeutics Inc.",
      "ma_probability_score": 87.5,
      "rank": 1
    },
    {
      "company_id": "COMP-23456",
      "company_name": "Beta Biopharma Ltd.",
      "ma_probability_score": 84.2,
      "rank": 2
    }
  ],
  "featured_matches": [
    {
      "match_id": "MATCH-2025-001",
      "target_name": "Acme Therapeutics Inc.",
      "acquirer_name": "Global Pharma Corporation",
      "match_score": 89.5,
      "rank": 1
    }
  ],
  "distribution_list": [
    {
      "recipient_id": "USR-001",
      "recipient_name": "Investment Committee",
      "recipient_email": "ic@investmentfirm.com",
      "delivery_method": "email"
    }
  ],
  "file_locations": [
    {
      "format": "pdf",
      "path": "/reports/2025/12/RPT-2025-12-001.pdf",
      "size_bytes": 2456789,
      "url": "https://storage.example.com/reports/RPT-2025-12-001.pdf"
    },
    {
      "format": "html",
      "path": "/reports/2025/12/RPT-2025-12-001.html",
      "size_bytes": 876543,
      "url": "https://portal.example.com/reports/RPT-2025-12-001"
    }
  ],
  "generation_metadata": {
    "generation_duration_ms": 3456,
    "template_version": "2.1.0",
    "data_sources": [
      "clinical-trial-signals",
      "patent-ip-intelligence",
      "insider-hiring-signals"
    ],
    "data_freshness": "2025-12-07T17:45:00.000Z"
  },
  "related_event_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440111",
    "770e8400-e29b-41d4-a716-446655440222"
  ],
  "notes": "Weekly summary generated successfully. All data sources current as of 5:45 PM UTC."
}
```

---

## Validation Rules

### Global Validation Rules

1. **UUID Format**: All event IDs, correlation IDs, and causation IDs MUST be valid UUID v4 format
2. **Date Formats**: All dates MUST be in ISO 8601 format (YYYY-MM-DD for dates, full ISO 8601 for timestamps)
3. **Score Ranges**: All score fields (impact_score, match_score, etc.) MUST be between 0 and 100 inclusive
4. **Required Fields**: All fields marked as "required" in the schema MUST be present
5. **Enum Values**: All enum fields MUST use only the specified values
6. **String Lengths**: All string fields with maxLength constraints MUST be enforced
7. **Ticker Symbols**: Stock ticker symbols MUST be 1-5 uppercase letters (pattern: ^[A-Z]{1,5}$)
8. **URLs**: All URL fields MUST be valid URIs

### Event-Specific Validation Rules

#### ClinicalTrialSignalEvent
- `trial_nct_id` MUST match pattern ^NCT\d{8}$
- `current_phase` MUST be later than or equal to `previous_phase` when signal_type is "phase_advancement"
- `impact_score` MUST be calculated based on: signal_type, current_phase, therapeutic_area
- `estimated_completion_date` MUST be in the future

#### PatentCliffEvent
- `days_until_expiration` MUST be calculated from current date to `expiration_date`
- `expiration_date` MUST be after `filing_date`
- `revenue_percentage` MUST be between 0 and 100
- `threat_level` MUST align with `days_until_expiration` and `revenue_percentage`

#### InsiderActivityEvent
- `transaction_date` MUST be before or equal to `filing_date`
- `total_value` SHOULD equal `shares_transacted` × `price_per_share` (within rounding tolerance)
- For activity_type "insider_buy", `transaction_code` SHOULD be "P"
- For activity_type "insider_sell", `transaction_code` SHOULD be "S"

#### HiringSignalEvent
- `effective_date` MUST be after or equal to `signal_date`
- For signal_type "executive_hire", `previous_company` SHOULD be provided
- For signal_type "executive_departure", `destination_company` SHOULD be provided

#### MACandidateEvent
- `ma_probability_score` MUST be derived from signal_summary aggregation
- `contributing_event_ids` array MUST contain at least one event ID
- `signal_summary` counts MUST match number of events in `contributing_event_ids`
- `estimated_valuation_range.low_usd` MUST be less than `estimated_valuation_range.high_usd`
- `timeline_estimate.earliest_date` ≤ `timeline_estimate.most_likely_date` ≤ `timeline_estimate.latest_date`

#### AcquirerMatchEvent
- `deal_size_percentage` MUST equal (`target_valuation_usd` / `acquirer_market_cap_usd`) × 100
- `match_score` MUST be calculated from therapeutic_alignment, technology_fit, financial_fit, and historical_precedent scores
- `probability_estimate` MUST be between 0 and 100
- `timeline_estimate.earliest_announcement` ≤ `timeline_estimate.most_likely_announcement` ≤ `timeline_estimate.latest_announcement`

#### ReportGeneratedEvent
- `reporting_period.start_date` MUST be before `reporting_period.end_date`
- `generation_date` MUST be after or equal to `reporting_period.end_date`
- At least one `output_format` MUST be specified
- `summary_statistics` counts MUST be non-negative integers

---

## Event Flow

### Signal Collection Flow

```
1. External Data Sources
   ↓
2. Signal Processors (clinical-trial-signals, patent-ip-intelligence, insider-hiring-signals)
   ↓
3. Emit Individual Signal Events (ClinicalTrialSignalEvent, PatentCliffEvent, etc.)
   ↓
4. Event Bus
   ↓
5. Signal Aggregation Service
   ↓
6. Emit MACandidateEvent (when threshold met)
   ↓
7. Matching Engine
   ↓
8. Emit AcquirerMatchEvent
   ↓
9. Report Generator
   ↓
10. Emit ReportGeneratedEvent
```

### Event Correlation

Events SHOULD be correlated using the following pattern:

1. **correlation_id**: Used to group all events related to a single company's M&A journey
2. **causation_id**: Used to link cause-and-effect relationships between events
3. **contributing_event_ids**: Used in MACandidateEvent and AcquirerMatchEvent to reference source signals

Example correlation flow:
```
ClinicalTrialSignalEvent (event_id: A, correlation_id: X)
  ↓
PatentCliffEvent (event_id: B, correlation_id: X)
  ↓
MACandidateEvent (event_id: C, correlation_id: X, contributing_event_ids: [A, B])
  ↓
AcquirerMatchEvent (event_id: D, correlation_id: X, causation_id: C)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-07 | Initial schema specification |

---

## Notes

- All events are immutable once published
- Event versioning follows semantic versioning (MAJOR.MINOR.PATCH)
- Breaking changes to event schemas require MAJOR version increment
- Consumers MUST handle unknown fields gracefully for forward compatibility
- Producers SHOULD NOT send fields not defined in the schema
- All monetary values are in USD unless otherwise specified
- All timestamps are in UTC timezone

---

**End of Event Schema Specifications**
