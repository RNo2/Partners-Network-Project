"""Import contracts. Identifiers are text, preserving leading zeroes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Dataset:
    fields: str
    required: str
    key: str
    numeric: str = ''
    dates: str = ''

SCHEMAS = {
 'partners': Dataset('partner_id site_name street_address city state zip_code county neighborhood census_tract latitude longitude partner_type active_status network_membership provider_affiliations source last_verified visibility', 'partner_id site_name network_membership active_status source visibility', 'partner_id', 'latitude longitude', 'last_verified'),
 'distribution_records': Dataset('record_id partner_id reporting_period_start reporting_period_end pounds_sent pounds_received pounds_distributed households_served individuals_served distribution_events distribution_frequency source visibility', 'record_id partner_id reporting_period_start reporting_period_end source visibility', 'record_id', 'pounds_sent pounds_received pounds_distributed households_served individuals_served distribution_events', 'reporting_period_start reporting_period_end'),
 'operating_schedules': Dataset('schedule_id partner_id operating_day opening_time closing_time distribution_frequency effective_start_date effective_end_date verification_status last_verified source visibility', 'schedule_id partner_id operating_day opening_time closing_time distribution_frequency verification_status source visibility', 'schedule_id', '', 'effective_start_date effective_end_date last_verified'),
 'community_indicators': Dataset('indicator_id indicator_name geographic_id geographic_resolution value unit numerator denominator source reporting_year vintage methodology visibility', 'indicator_id indicator_name geographic_id geographic_resolution value unit source reporting_year vintage methodology visibility', 'indicator_id', 'value numerator denominator reporting_year'),
 'geographic_units': Dataset('unit_id geographic_id geographic_resolution name county geometry_json source vintage visibility', 'unit_id geographic_id geographic_resolution name geometry_json source vintage visibility', 'unit_id'),
 'accessibility_measurements': Dataset('measurement_id origin_geographic_id destination_partner_id travel_mode measurement_type travel_minutes distance_km time_of_day operating_day reporting_date source visibility', 'measurement_id origin_geographic_id destination_partner_id travel_mode measurement_type reporting_date source visibility', 'measurement_id', 'travel_minutes distance_km', 'reporting_date'),
 'operational_constraints': Dataset('constraint_id geographic_id partner_id dimension quantity unit qualitative_notes reporting_date source visibility', 'constraint_id dimension reporting_date source visibility', 'constraint_id', 'quantity', 'reporting_date'),
 'assessment_criteria': Dataset('criterion_id label definition rating_guidance framework_version approval_status source visibility', 'criterion_id label definition framework_version approval_status source visibility', 'criterion_id'),
 'partner_assessments': Dataset('assessment_id partner_id criterion_id framework_version rating qualitative_notes additional_services community_reach assessment_date review_status source visibility', 'assessment_id partner_id framework_version assessment_date review_status source visibility', 'assessment_id', '', 'assessment_date'),
}
ENUMS = {
 'visibility': ['internal', 'public'],
 'network_membership': ['share', 'external', 'unknown'],
 'active_status': ['active', 'inactive', 'unknown'],
 'verification_status': ['verified', 'unverified', 'unknown'],
 'geographic_resolution': ['county', 'zip', 'neighborhood', 'tract'],
 'operating_day': ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],
 'measurement_type': ['network', 'straight_line'],
 'travel_mode': ['walking','transit','driving','straight_line'],
 'approval_status': ['draft','approved','retired'],
 'review_status': ['draft','in_review','final'],
}
DESCRIPTIONS = {
 'network_membership': 'Explicit affiliation: share, external, unknown. Never inferred from a name.',
 'visibility': 'internal or public. Public requires permission to disclose; assessments and operational/distribution records are internal only.',
 'geometry_json': 'GeoJSON Polygon/MultiPolygon geometry in EPSG:4326; no invented crosswalks.',
 'distribution_frequency': 'Source wording, e.g. weekly or first Monday. Non-weekly schedules are not treated as weekly.',
 'value': 'Measured value, never a missing-value substitute. Rate units: percent, fraction, count.',
 'rating': 'Source-provided qualitative rating under a matching approved criterion; no generated score.',
 'reporting_period_start': 'Inclusive ISO date. Exact interval retained; incompatible periods are never summed together.',
 'source': 'Traceable dataset title/URL or internal owner. Not automatically verified by import.',
 'last_verified': 'ISO date of actual verification; blank means unknown.',
 'partner_type': 'Configurable free text: pantry, community fridge, free meal program, etc.',
 'provider_affiliations': 'Semicolon-separated source-reported affiliations.',
}
