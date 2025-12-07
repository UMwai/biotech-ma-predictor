"""
Target Identifier - Main orchestration for target identification

Combines screening, ranking, and watchlist generation to identify
and analyze potential biotech acquisition targets.
"""

from typing import List, Dict, Optional
from datetime import datetime, date
from .screener import (
    TargetScreener,
    ScreeningCriteria,
    CompanyProfile,
    TherapeuticArea,
    DevelopmentPhase
)
from .ranker import TargetRanker, RankingWeights
from .watchlist import (
    AcquisitionTarget,
    AcquirerMatch,
    ValuationRange,
    WatchlistManager,
    RankedWatchlist,
    AcquirerType,
    DataCatalyst
)


class TargetIdentifier:
    """
    Main target identification engine

    Orchestrates the full pipeline:
    1. Screen universe of companies
    2. Rank by M&A attractiveness
    3. Generate detailed target profiles
    4. Create ranked watchlists
    """

    def __init__(
        self,
        screening_criteria: Optional[ScreeningCriteria] = None,
        ranking_weights: Optional[RankingWeights] = None
    ):
        """
        Initialize identifier with optional custom criteria and weights

        Args:
            screening_criteria: Custom ScreeningCriteria
            ranking_weights: Custom RankingWeights
        """
        self.screener = TargetScreener(screening_criteria)
        self.ranker = TargetRanker(ranking_weights)
        self.watchlist_manager = WatchlistManager()

    def identify_targets(
        self,
        universe: List[Dict],
        top_n: Optional[int] = 20
    ) -> RankedWatchlist:
        """
        Run full identification pipeline

        Args:
            universe: List of company data dicts
            top_n: Number of top targets to return

        Returns:
            RankedWatchlist with identified targets
        """
        # Step 1: Screen companies
        company_profiles = [self._dict_to_profile(c) for c in universe]
        screening_results = self.screener.batch_screen(company_profiles)

        passed_companies = [
            result['company'] for result in screening_results['passed']
        ]

        # Step 2: Convert to ranking format and rank
        ranking_data = [self._profile_to_ranking_data(p) for p in passed_companies]
        ranked_targets = self.ranker.rank_targets(ranking_data, top_n=top_n)

        # Step 3: Create detailed target profiles
        acquisition_targets = []
        for ranked_target in ranked_targets:
            # Find original company data
            company_data = next(
                c for c in universe if c['ticker'] == ranked_target.ticker
            )

            target = self._create_acquisition_target(
                company_data,
                ranked_target
            )
            acquisition_targets.append(target)

        # Step 4: Create watchlist
        watchlist = RankedWatchlist(
            name=f"Top {len(acquisition_targets)} Targets - {datetime.now().strftime('%Y-%m-%d')}",
            description="Algorithmically identified M&A targets",
            targets=acquisition_targets
        )

        return watchlist

    def _dict_to_profile(self, data: Dict) -> CompanyProfile:
        """Convert data dict to CompanyProfile"""
        return CompanyProfile(
            ticker=data['ticker'],
            name=data['name'],
            market_cap=data['market_cap'],
            cash_position=data.get('cash_position', 0),
            quarterly_burn_rate=data.get('quarterly_burn_rate', 0),
            lead_asset=data.get('lead_asset'),
            lead_asset_phase=DevelopmentPhase(data.get('lead_asset_phase', 'Preclinical')),
            therapeutic_areas=[
                TherapeuticArea(area) for area in data.get('therapeutic_areas', [])
            ],
            total_pipeline_assets=data.get('total_pipeline_assets', 0),
            recent_catalysts=data.get('recent_catalysts', []),
            ipo_date=data.get('ipo_date'),
            region=data.get('region', 'North America'),
            stock_return_52w=data.get('stock_return_52w', 0),
            stock_return_ytd=data.get('stock_return_ytd', 0),
            institutional_ownership=data.get('institutional_ownership', 0.5),
            is_royalty_company=data.get('is_royalty_company', False),
            has_approved_products=data.get('has_approved_products', False),
            is_platform_company=data.get('is_platform_company', False)
        )

    def _profile_to_ranking_data(self, profile: CompanyProfile) -> Dict:
        """Convert CompanyProfile to ranking data dict"""
        return {
            'ticker': profile.ticker,
            'name': profile.name,
            'market_cap': profile.market_cap,
            'cash_runway_months': profile.cash_runway_months,
            'lead_asset_phase': profile.lead_asset_phase.value,
            'therapeutic_areas': [area.value for area in profile.therapeutic_areas],
            'total_pipeline_assets': profile.total_pipeline_assets,
            'stock_return_52w': profile.stock_return_52w,
            'institutional_ownership': profile.institutional_ownership,
            # Add additional fields for ranking
            'has_positive_phase2_data': True,  # Would come from real data
            'has_differentiated_moa': True,
            'num_likely_acquirers': 3,
            'fills_portfolio_gap': True,
            'months_to_next_catalyst': 6,
            'num_catalysts_12mo': 2,
            'competitive_position': 'fast_follower',
            'num_direct_competitors': 5,
            'regulatory_complexity': 'medium'
        }

    def _create_acquisition_target(
        self,
        company_data: Dict,
        ranked_target
    ) -> AcquisitionTarget:
        """Create detailed AcquisitionTarget from company data and ranking"""

        # Create acquirer matches
        likely_acquirers = self._generate_acquirer_matches(company_data)

        # Create valuation range
        market_cap = company_data['market_cap']
        estimated_deal_value = ValuationRange(
            low=market_cap * 1.3,  # 30% premium
            base=market_cap * 1.5,  # 50% premium
            high=market_cap * 1.8   # 80% premium
        )

        # Create catalysts
        catalysts = self._generate_catalysts(company_data)

        # Calculate deal probability
        deal_prob_12mo = self._calculate_deal_probability(
            ranked_target.composite_score,
            company_data
        )

        return AcquisitionTarget(
            ticker=company_data['ticker'],
            name=company_data['name'],
            description=company_data.get('description', ''),
            therapeutic_area=company_data.get('therapeutic_areas', [''])[0],
            therapeutic_areas_list=company_data.get('therapeutic_areas', []),
            lead_asset=company_data.get('lead_asset', ''),
            lead_asset_indication=company_data.get('lead_asset_indication', ''),
            development_stage=company_data.get('lead_asset_phase', ''),
            market_cap=company_data['market_cap'],
            enterprise_value=company_data.get('enterprise_value', market_cap),
            cash_position=company_data.get('cash_position', 0),
            cash_runway_months=company_data.get('cash_runway_months', 0),
            quarterly_burn_rate=company_data.get('quarterly_burn_rate', 0),
            stock_price=company_data.get('stock_price', 0),
            stock_return_52w=company_data.get('stock_return_52w', 0),
            stock_return_ytd=company_data.get('stock_return_ytd', 0),
            institutional_ownership=company_data.get('institutional_ownership', 0),
            ma_score=ranked_target.composite_score,
            rank=ranked_target.rank,
            percentile=ranked_target.percentile,
            factor_scores=ranked_target.factor_scores.to_dict(),
            key_strengths=ranked_target.key_strengths,
            key_weaknesses=ranked_target.key_weaknesses,
            dcf_valuation=company_data.get('dcf_valuation', 0),
            comparable_valuation=company_data.get('comparable_valuation', 0),
            analyst_price_target_avg=company_data.get('analyst_pt_avg', 0),
            deal_probability_12mo=deal_prob_12mo,
            deal_probability_24mo=min(deal_prob_12mo * 1.6, 0.95),
            estimated_deal_value=estimated_deal_value,
            implied_premium=50.0,  # Base case
            likely_acquirers=likely_acquirers,
            upcoming_catalysts=catalysts,
            investment_thesis=ranked_target.investment_thesis,
            risk_factors=company_data.get('risk_factors', []),
            recent_developments=company_data.get('recent_developments', [])
        )

    def _generate_acquirer_matches(self, company_data: Dict) -> List[AcquirerMatch]:
        """Generate likely acquirer matches based on therapeutic area"""

        therapeutic_area = company_data.get('therapeutic_areas', [''])[0]

        # Map therapeutic areas to likely acquirers
        acquirer_map = {
            'obesity_glp1': [
                ('Novo Nordisk', AcquirerType.BIG_PHARMA, 95, 'Leader in metabolic disease'),
                ('Eli Lilly', AcquirerType.BIG_PHARMA, 90, 'Strong GLP-1 portfolio'),
                ('Roche', AcquirerType.BIG_PHARMA, 75, 'Expanding metabolic franchise'),
                ('AstraZeneca', AcquirerType.BIG_PHARMA, 70, 'Cardiometabolic focus')
            ],
            'oncology_adc': [
                ('Daiichi Sankyo', AcquirerType.BIG_PHARMA, 95, 'ADC pioneer and leader'),
                ('AbbVie', AcquirerType.BIG_PHARMA, 85, 'Building ADC portfolio'),
                ('Merck', AcquirerType.BIG_PHARMA, 80, 'Expanding beyond keytruda'),
                ('Gilead', AcquirerType.BIG_PHARMA, 75, 'Oncology growth strategy')
            ],
            'radiopharmaceuticals': [
                ('Novartis', AcquirerType.BIG_PHARMA, 90, 'Radioligand leader (Pluvicto)'),
                ('Eli Lilly', AcquirerType.BIG_PHARMA, 85, 'Recent radioligand entry'),
                ('Bristol Myers Squibb', AcquirerType.BIG_PHARMA, 75, 'Diversifying oncology'),
                ('AstraZeneca', AcquirerType.BIG_PHARMA, 70, 'Oncology focus')
            ],
            'autoimmune': [
                ('Johnson & Johnson', AcquirerType.BIG_PHARMA, 90, 'Immunology leader'),
                ('AbbVie', AcquirerType.BIG_PHARMA, 85, 'Post-Humira diversification'),
                ('Amgen', AcquirerType.BIG_PHARMA, 80, 'Inflammation expertise'),
                ('UCB', AcquirerType.SPECIALTY_PHARMA, 75, 'Immunology specialist')
            ],
            'cns_neuropsychiatry': [
                ('AbbVie', AcquirerType.BIG_PHARMA, 90, 'Recent CNS acquisitions'),
                ('Bristol Myers Squibb', AcquirerType.BIG_PHARMA, 85, 'Acquired Karuna'),
                ('Takeda', AcquirerType.BIG_PHARMA, 80, 'CNS focus area'),
                ('Otsuka', AcquirerType.SPECIALTY_PHARMA, 70, 'Psychiatry leader')
            ],
            'rare_disease': [
                ('Sanofi', AcquirerType.BIG_PHARMA, 85, 'Rare disease strategy'),
                ('Takeda', AcquirerType.BIG_PHARMA, 80, 'Rare disease leader'),
                ('Ultragenyx', AcquirerType.LARGE_BIOTECH, 75, 'Rare disease specialist'),
                ('BioMarin', AcquirerType.LARGE_BIOTECH, 70, 'Rare disease pure play')
            ]
        }

        acquirer_specs = acquirer_map.get(therapeutic_area, [
            ('Pfizer', AcquirerType.BIG_PHARMA, 70, 'Broad therapeutic interests'),
            ('Roche', AcquirerType.BIG_PHARMA, 65, 'Innovation focused'),
            ('Merck', AcquirerType.BIG_PHARMA, 60, 'Portfolio diversification')
        ])

        acquirers = []
        for name, acq_type, fit_score, rationale in acquirer_specs:
            acquirers.append(AcquirerMatch(
                name=name,
                acquirer_type=acq_type,
                strategic_fit_score=fit_score,
                rationale=rationale,
                fills_portfolio_gap=True,
                therapeutic_area_overlap=True,
                probability=fit_score / 100 * 0.4,  # Scale to 0-0.4
                estimated_premium=40 + (fit_score / 100) * 20  # 40-60% premium
            ))

        return acquirers

    def _generate_catalysts(self, company_data: Dict) -> List[DataCatalyst]:
        """Generate upcoming catalysts"""
        catalysts = []

        # Would be populated from real data
        # Placeholder example
        if company_data.get('has_phase3_ongoing'):
            catalysts.append(DataCatalyst(
                event_type="Phase 3 Topline Data",
                expected_date=date(2025, 6, 30),
                asset_name=company_data.get('lead_asset', 'Lead Asset'),
                importance="Critical"
            ))

        if company_data.get('has_phase2_ongoing'):
            catalysts.append(DataCatalyst(
                event_type="Phase 2 Data",
                expected_date=date(2025, 9, 30),
                asset_name=company_data.get('lead_asset', 'Lead Asset'),
                importance="High"
            ))

        return catalysts

    def _calculate_deal_probability(
        self,
        ma_score: float,
        company_data: Dict
    ) -> float:
        """
        Calculate 12-month deal probability

        Based on M&A score and other factors
        """
        # Base probability from M&A score
        base_prob = ma_score / 100 * 0.5  # Max 50% from score

        # Adjust for cash runway
        runway = company_data.get('cash_runway_months', 999)
        if runway < 15:
            base_prob += 0.20
        elif runway < 24:
            base_prob += 0.15
        elif runway < 36:
            base_prob += 0.05

        # Adjust for stock performance
        stock_return = company_data.get('stock_return_52w', 0)
        if stock_return < -40:
            base_prob += 0.10

        # Adjust for activist/rumors
        if company_data.get('has_activist_investor'):
            base_prob += 0.15
        if company_data.get('has_takeover_rumors'):
            base_prob += 0.10

        return min(base_prob, 0.85)  # Cap at 85%

    def generate_sample_watchlist(self) -> RankedWatchlist:
        """
        Generate sample watchlist with realistic biotech targets

        Returns:
            RankedWatchlist with 15-20 realistic targets based on 2024-2025 data
        """
        sample_companies = self._get_sample_company_data()
        return self.identify_targets(sample_companies, top_n=20)

    def _get_sample_company_data(self) -> List[Dict]:
        """Get sample company data for realistic targets"""

        return [
            # OBESITY / GLP-1
            {
                'ticker': 'GPCR',
                'name': 'Structure Therapeutics',
                'description': 'Oral GLP-1 receptor agonist developer',
                'market_cap': 3_200_000_000,
                'cash_position': 450_000_000,
                'quarterly_burn_rate': 45_000_000,
                'cash_runway_months': 30,
                'lead_asset': 'GSBR-1290',
                'lead_asset_indication': 'Obesity',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['obesity_glp1'],
                'total_pipeline_assets': 2,
                'stock_price': 42.50,
                'stock_return_52w': -15.0,
                'stock_return_ytd': 25.0,
                'institutional_ownership': 0.75,
                'has_positive_phase2_data': True,
                'has_differentiated_moa': True,
                'has_novel_moa': False,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 4,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 4,
                'num_catalysts_12mo': 2,
                'competitive_position': 'fast_follower',
                'num_direct_competitors': 8,
                'recent_developments': ['Positive Phase 2 data', 'Oral formulation advantage']
            },
            {
                'ticker': 'VKTX',
                'name': 'Viking Therapeutics',
                'description': 'GLP-1/GIP dual agonist developer',
                'market_cap': 6_800_000_000,
                'cash_position': 850_000_000,
                'quarterly_burn_rate': 35_000_000,
                'cash_runway_months': 73,
                'lead_asset': 'VK2735',
                'lead_asset_indication': 'Obesity',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['obesity_glp1'],
                'total_pipeline_assets': 3,
                'stock_price': 68.00,
                'stock_return_52w': 320.0,
                'stock_return_ytd': 285.0,
                'institutional_ownership': 0.62,
                'has_positive_phase2_data': True,
                'has_differentiated_moa': True,
                'num_likely_acquirers': 5,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 6,
                'competitive_position': 'co_leader',
                'num_direct_competitors': 6
            },
            {
                'ticker': 'ALT',
                'name': 'Altimmune',
                'description': 'GLP-1/glucagon dual agonist',
                'market_cap': 950_000_000,
                'cash_position': 180_000_000,
                'quarterly_burn_rate': 25_000_000,
                'cash_runway_months': 22,
                'lead_asset': 'Pemvidutide',
                'lead_asset_indication': 'Obesity/NASH',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['obesity_glp1'],
                'total_pipeline_assets': 2,
                'stock_return_52w': 45.0,
                'institutional_ownership': 0.58,
                'has_positive_phase2_data': True,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 5
            },

            # ONCOLOGY ADC
            {
                'ticker': 'ELEV',
                'name': 'Elevation Oncology',
                'description': 'Genomically-defined oncology targets',
                'market_cap': 620_000_000,
                'cash_position': 125_000_000,
                'quarterly_burn_rate': 18_000_000,
                'cash_runway_months': 21,
                'lead_asset': 'Seribantumab',
                'lead_asset_indication': 'NRG1+ Cancers',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['oncology_adc'],
                'total_pipeline_assets': 2,
                'stock_return_52w': -35.0,
                'institutional_ownership': 0.68,
                'has_positive_phase2_data': True,
                'num_likely_acquirers': 4,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 3,
                'competitive_position': 'leader'
            },
            {
                'ticker': 'CMPX',
                'name': 'Compass Therapeutics',
                'description': 'Bispecific antibody developer',
                'market_cap': 480_000_000,
                'cash_position': 95_000_000,
                'quarterly_burn_rate': 15_000_000,
                'cash_runway_months': 19,
                'lead_asset': 'CTX-009',
                'lead_asset_indication': 'Biliary Tract Cancer',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['oncology_adc'],
                'total_pipeline_assets': 3,
                'stock_return_52w': -42.0,
                'institutional_ownership': 0.55,
                'num_likely_acquirers': 3,
                'months_to_next_catalyst': 4
            },

            # RADIOPHARMACEUTICALS
            {
                'ticker': 'FUSN',
                'name': 'Fusion Pharmaceuticals',
                'description': 'Radioconjugates for cancer',
                'market_cap': 850_000_000,
                'cash_position': 165_000_000,
                'quarterly_burn_rate': 22_000_000,
                'cash_runway_months': 23,
                'lead_asset': 'FPI-1434',
                'lead_asset_indication': 'Solid Tumors',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['radiopharmaceuticals'],
                'total_pipeline_assets': 4,
                'stock_return_52w': -18.0,
                'institutional_ownership': 0.72,
                'has_positive_phase2_data': True,
                'has_novel_moa': True,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 4,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 5,
                'competitive_position': 'co_leader'
            },
            {
                'ticker': 'AURA',
                'name': 'Aura Biosciences',
                'description': 'Virus-like drug conjugates',
                'market_cap': 725_000_000,
                'cash_position': 140_000_000,
                'quarterly_burn_rate': 20_000_000,
                'cash_runway_months': 21,
                'lead_asset': 'AU-011',
                'lead_asset_indication': 'Ocular Melanoma',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['radiopharmaceuticals', 'rare_disease'],
                'total_pipeline_assets': 2,
                'stock_return_52w': -28.0,
                'institutional_ownership': 0.65,
                'has_phase3_ongoing': True,
                'num_likely_acquirers': 3,
                'months_to_next_catalyst': 8
            },

            # AUTOIMMUNE
            {
                'ticker': 'ANNX',
                'name': 'Annexon Biosciences',
                'description': 'Complement inhibitors',
                'market_cap': 890_000_000,
                'cash_position': 180_000_000,
                'quarterly_burn_rate': 28_000_000,
                'cash_runway_months': 19,
                'lead_asset': 'ANX005',
                'lead_asset_indication': 'Autoimmune diseases',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['autoimmune'],
                'total_pipeline_assets': 3,
                'stock_return_52w': -52.0,
                'institutional_ownership': 0.70,
                'has_phase3_ongoing': True,
                'has_novel_moa': True,
                'num_likely_acquirers': 4,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 6,
                'competitive_position': 'fast_follower'
            },
            {
                'ticker': 'XNCR',
                'name': 'Xencor',
                'description': 'Engineered monoclonal antibodies',
                'market_cap': 1_450_000_000,
                'cash_position': 285_000_000,
                'quarterly_burn_rate': 32_000_000,
                'cash_runway_months': 27,
                'lead_asset': 'Plamotamab',
                'lead_asset_indication': 'B-cell malignancies',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['autoimmune', 'oncology_adc'],
                'total_pipeline_assets': 8,
                'stock_return_52w': -38.0,
                'institutional_ownership': 0.82,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 5,
                'months_to_next_catalyst': 4
            },

            # CNS / NEUROPSYCHIATRY
            {
                'ticker': 'PRAX',
                'name': 'Praxis Precision Medicines',
                'description': 'CNS disorder treatments',
                'market_cap': 1_280_000_000,
                'cash_position': 240_000_000,
                'quarterly_burn_rate': 35_000_000,
                'cash_runway_months': 21,
                'lead_asset': 'Ulixacaltamide',
                'lead_asset_indication': 'Essential Tremor',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['cns_neuropsychiatry'],
                'total_pipeline_assets': 4,
                'stock_return_52w': -45.0,
                'institutional_ownership': 0.75,
                'has_phase3_ongoing': True,
                'has_positive_phase2_data': True,
                'num_likely_acquirers': 4,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 9,
                'competitive_position': 'leader'
            },
            {
                'ticker': 'SAGE',
                'name': 'Sage Therapeutics',
                'description': 'CNS disorders',
                'market_cap': 1_650_000_000,
                'cash_position': 520_000_000,
                'quarterly_burn_rate': 95_000_000,
                'cash_runway_months': 16,
                'lead_asset': 'Zuranolone',
                'lead_asset_indication': 'Depression',
                'lead_asset_phase': 'Approved',
                'therapeutic_areas': ['cns_neuropsychiatry'],
                'total_pipeline_assets': 3,
                'stock_return_52w': -72.0,
                'institutional_ownership': 0.88,
                'has_approved_products': True,
                'num_likely_acquirers': 3,
                'months_to_next_catalyst': 3,
                'has_activist_investor': True
            },

            # RARE DISEASE
            {
                'ticker': 'TBPH',
                'name': 'Theratechnologies',
                'description': 'Rare metabolic diseases',
                'market_cap': 580_000_000,
                'cash_position': 85_000_000,
                'quarterly_burn_rate': 18_000_000,
                'cash_runway_months': 14,
                'lead_asset': 'Tesamorelin',
                'lead_asset_indication': 'NASH',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['rare_disease'],
                'total_pipeline_assets': 2,
                'stock_return_52w': -48.0,
                'institutional_ownership': 0.45,
                'has_phase3_ongoing': True,
                'num_likely_acquirers': 3,
                'months_to_next_catalyst': 7
            },
            {
                'ticker': 'KRYS',
                'name': 'Krystal Biotech',
                'description': 'Gene therapy platform',
                'market_cap': 4_800_000_000,
                'cash_position': 520_000_000,
                'quarterly_burn_rate': 42_000_000,
                'cash_runway_months': 37,
                'lead_asset': 'Vyjuvek',
                'lead_asset_indication': 'Dystrophic EB',
                'lead_asset_phase': 'Approved',
                'therapeutic_areas': ['rare_disease', 'gene_therapy'],
                'total_pipeline_assets': 5,
                'stock_return_52w': 55.0,
                'institutional_ownership': 0.82,
                'has_approved_products': True,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 5,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 5
            },

            # IMMUNOLOGY
            {
                'ticker': 'IMCR',
                'name': 'Immunocore Holdings',
                'description': 'TCR-based therapeutics',
                'market_cap': 2_350_000_000,
                'cash_position': 310_000_000,
                'quarterly_burn_rate': 38_000_000,
                'cash_runway_months': 25,
                'lead_asset': 'Kimmtrak',
                'lead_asset_indication': 'Uveal Melanoma',
                'lead_asset_phase': 'Approved',
                'therapeutic_areas': ['immunology', 'oncology_adc'],
                'total_pipeline_assets': 6,
                'stock_return_52w': 85.0,
                'institutional_ownership': 0.78,
                'has_approved_products': True,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 4,
                'months_to_next_catalyst': 4
            },
            {
                'ticker': 'BLUE',
                'name': 'bluebird bio',
                'description': 'Gene therapies',
                'market_cap': 780_000_000,
                'cash_position': 145_000_000,
                'quarterly_burn_rate': 55_000_000,
                'cash_runway_months': 8,
                'lead_asset': 'Lyfgenia',
                'lead_asset_indication': 'Sickle Cell Disease',
                'lead_asset_phase': 'Approved',
                'therapeutic_areas': ['gene_therapy', 'rare_disease'],
                'total_pipeline_assets': 3,
                'stock_return_52w': -68.0,
                'institutional_ownership': 0.52,
                'has_approved_products': True,
                'num_likely_acquirers': 4,
                'months_to_next_catalyst': 2,
                'has_activist_investor': True
            },

            # ADDITIONAL TARGETS
            {
                'ticker': 'RVMD',
                'name': 'Revolution Medicines',
                'description': 'RAS inhibitor oncology',
                'market_cap': 7_200_000_000,
                'cash_position': 1_100_000_000,
                'quarterly_burn_rate': 85_000_000,
                'cash_runway_months': 39,
                'lead_asset': 'RMC-6236',
                'lead_asset_indication': 'RAS+ Cancers',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['oncology_adc'],
                'total_pipeline_assets': 4,
                'stock_return_52w': 120.0,
                'institutional_ownership': 0.85,
                'has_positive_phase2_data': True,
                'has_novel_moa': True,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 6,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 5,
                'competitive_position': 'leader'
            },
            {
                'ticker': 'REPL',
                'name': 'Replimune Group',
                'description': 'Oncolytic immunotherapy',
                'market_cap': 1_150_000_000,
                'cash_position': 220_000_000,
                'quarterly_burn_rate': 32_000_000,
                'cash_runway_months': 21,
                'lead_asset': 'RP1',
                'lead_asset_indication': 'Melanoma',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['oncology_adc', 'immunology'],
                'total_pipeline_assets': 3,
                'stock_return_52w': -22.0,
                'institutional_ownership': 0.72,
                'has_phase3_ongoing': True,
                'num_likely_acquirers': 4,
                'months_to_next_catalyst': 10
            },
            {
                'ticker': 'AKRO',
                'name': 'Akero Therapeutics',
                'description': 'NASH therapeutics',
                'market_cap': 2_450_000_000,
                'cash_position': 380_000_000,
                'quarterly_burn_rate': 48_000_000,
                'cash_runway_months': 24,
                'lead_asset': 'Efruxifermin',
                'lead_asset_indication': 'NASH',
                'lead_asset_phase': 'Phase 3',
                'therapeutic_areas': ['cardiovascular'],
                'total_pipeline_assets': 2,
                'stock_return_52w': 42.0,
                'institutional_ownership': 0.80,
                'has_phase3_ongoing': True,
                'has_positive_phase2_data': True,
                'num_likely_acquirers': 5,
                'fills_portfolio_gap': True,
                'months_to_next_catalyst': 12,
                'competitive_position': 'co_leader'
            },
            {
                'ticker': 'RLAY',
                'name': 'Relay Therapeutics',
                'description': 'Precision oncology',
                'market_cap': 1_850_000_000,
                'cash_position': 410_000_000,
                'quarterly_burn_rate': 55_000_000,
                'cash_runway_months': 22,
                'lead_asset': 'RLY-2608',
                'lead_asset_indication': 'Solid Tumors',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['oncology_adc'],
                'total_pipeline_assets': 5,
                'stock_return_52w': -42.0,
                'institutional_ownership': 0.78,
                'has_proprietary_platform': True,
                'num_likely_acquirers': 4,
                'months_to_next_catalyst': 6
            },
            {
                'ticker': 'IGMS',
                'name': 'IGM Biosciences',
                'description': 'IgM antibody therapeutics',
                'market_cap': 680_000_000,
                'cash_position': 165_000_000,
                'quarterly_burn_rate': 35_000_000,
                'cash_runway_months': 14,
                'lead_asset': 'Imvotamab',
                'lead_asset_indication': 'B-cell NHL',
                'lead_asset_phase': 'Phase 2',
                'therapeutic_areas': ['oncology_adc', 'immunology'],
                'total_pipeline_assets': 4,
                'stock_return_52w': -58.0,
                'institutional_ownership': 0.65,
                'has_proprietary_platform': True,
                'has_positive_phase2_data': True,
                'num_likely_acquirers': 3,
                'months_to_next_catalyst': 5,
                'has_activist_investor': False
            }
        ]
