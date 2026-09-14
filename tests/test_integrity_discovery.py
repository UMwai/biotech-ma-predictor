from src.research.integrity_discovery import (
    MarketClinicalAsset,
    is_distinctive_asset_name,
    match_publications_to_assets,
    parse_pubmed_integrity_records,
)


PUBMED_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2025</Year><Month>Nov</Month></PubDate>
          </JournalIssue>
          <Title>Journal of Tests</Title>
        </Journal>
        <ArticleTitle>Trial of EX-101 in a rare disease</ArticleTitle>
        <Abstract><AbstractText>EX-101 was compared with placebo.</AbstractText></Abstract>
        <PublicationTypeList>
          <PublicationType>Retracted Publication</PublicationType>
        </PublicationTypeList>
      </Article>
      <DataBankList>
        <DataBank>
          <DataBankName>ClinicalTrials.gov</DataBankName>
          <AccessionNumberList>
            <AccessionNumber>NCT00000001</AccessionNumber>
          </AccessionNumberList>
        </DataBank>
      </DataBankList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def asset(asset_id="clinical:EX-101", nct_id="NCT00000001"):
    return MarketClinicalAsset(
        asset_id=asset_id,
        asset_name="EX-101",
        owner_name="Example Bio",
        owner_ticker="EXMP",
        nct_id=nct_id,
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        owner_match_confidence=1.0,
    )


def test_parse_pubmed_integrity_record():
    records = parse_pubmed_integrity_records(PUBMED_XML)
    assert len(records) == 1
    assert records[0].pmid == "12345678"
    assert records[0].nct_ids == ["NCT00000001"]
    assert records[0].evidence_status == "publication_retraction"


def test_nct_match_has_priority_over_term_match():
    candidates = match_publications_to_assets(
        parse_pubmed_integrity_records(PUBMED_XML),
        [asset()],
    )
    assert len(candidates) == 1
    assert candidates[0].match_method == "nct_id"
    assert candidates[0].match_confidence == 1.0
    assert candidates[0].owner_match_confidence == 1.0
    assert "does not" in candidates[0].interpretation


def test_exact_asset_name_creates_lower_confidence_candidate():
    candidates = match_publications_to_assets(
        parse_pubmed_integrity_records(PUBMED_XML),
        [asset(asset_id="clinical:EX-101-other", nct_id="NCT99999999")],
        include_name_matches=True,
    )
    assert len(candidates) == 1
    assert candidates[0].match_method == "asset_name_exact_phrase"
    assert candidates[0].match_confidence == 0.70
    assert candidates[0].nct_id == ""


def test_generic_and_common_asset_names_are_not_distinctive():
    assert is_distinctive_asset_name("Control", "control", 1) is False
    assert is_distinctive_asset_name("Cisplatin", "cisplatin", 20) is False
    assert is_distinctive_asset_name("EX-101", "ex 101", 1) is True
    assert is_distinctive_asset_name("deramiocel", "deramiocel", 1) is True
