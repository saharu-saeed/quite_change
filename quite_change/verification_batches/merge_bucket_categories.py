# -*- coding: utf-8 -*-
"""Inject the `bucket` field into each non-IT sector entry based on the categorization
agents' output. Also writes a sector_buckets.json with label definitions that the build
script will pick up via _EXTRA_BUCKETS."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data")

ASSIGNMENTS = {
    "company_research_air_transport_sector.json": {
        "9201": "major_record_fuel_cliff",
        "9202": "major_record_fuel_cliff",
        "9204": "mid_tier_structural_squeeze",
        "9206": "mid_tier_structural_squeeze",
    },
    "company_research_mining_sector.json": {
        "1514": "investment_income_driven",
        "1515": "investment_income_driven",
        "1518": "post_coal_reinvention",
        "1663": "niche_commodity_operator",
    },
    "company_research_petroleum_sector.json": {
        "5009": "diversified_small_energy",
        "5019": "major_refiner",
        "5020": "major_refiner",
        "5021": "major_refiner",
        "5011": "infra_asphalt",
        "5015": "specialty_lubricant",
        "5018": "specialty_lubricant",
    },
    "company_research_marine_sector.json": {
        "9104": "profit_compressed_international",
        "9130": "profit_compressed_international",
        "9171": "domestic_modal_shift_rerating",
    },
    "company_research_land_transport_sector.json": {
        "9020": "inbound_tourism_play","9021": "inbound_tourism_play","9022": "inbound_tourism_play","9001": "inbound_tourism_play",
        "9003": "redevelopment_play","9007": "inbound_tourism_play","9031": "redevelopment_play","9041": "inbound_tourism_play",
        "9042": "inbound_tourism_play","9044": "inbound_tourism_play","9045": "inbound_tourism_play","9052": "inbound_tourism_play",
        "9069": "logistics_rate_hike_winner","9072": "auto_logistics_specialist","9066": "one_off_profit_collapse",
        "9090": "logistics_rate_hike_winner","9147": "logistics_rate_hike_winner","9005": "redevelopment_play",
        "9008": "redevelopment_play","9009": "one_off_profit_collapse","9024": "one_off_profit_collapse",
        "9006": "redevelopment_play","9048": "redevelopment_play","9064": "one_off_profit_collapse",
        "9065": "regional_quiet_compounder","9039": "auto_logistics_specialist","2384": "logistics_rate_hike_winner",
        "9010": "inbound_tourism_play","9012": "inbound_tourism_play","9017": "regional_quiet_compounder",
        "9023": "inbound_tourism_play","9025": "logistics_rate_hike_winner","9027": "regional_quiet_compounder",
        "9028": "auto_logistics_specialist","9029": "logistics_rate_hike_winner","9033": "inbound_tourism_play",
        "9034": "regional_quiet_compounder","9035": "inbound_tourism_play","9036": "logistics_rate_hike_winner",
        "9037": "logistics_rate_hike_winner","9040": "regional_quiet_compounder","9046": "inbound_tourism_play",
        "9049": "inbound_tourism_play","9051": "logistics_rate_hike_winner","9057": "logistics_rate_hike_winner",
        "9059": "regional_quiet_compounder","9060": "logistics_rate_hike_winner","9063": "regional_quiet_compounder",
        "9068": "logistics_rate_hike_winner","9073": "logistics_rate_hike_winner","9074": "logistics_rate_hike_winner",
        "9075": "logistics_rate_hike_winner","9076": "logistics_rate_hike_winner","9081": "regional_quiet_compounder",
        "9082": "inbound_tourism_play","9083": "inbound_tourism_play","9085": "inbound_tourism_play",
        "9087": "logistics_rate_hike_winner","9142": "inbound_tourism_play","9143": "logistics_rate_hike_winner",
        "9145": "auto_logistics_specialist",
    },
}

total = 0
for fname, tickers in ASSIGNMENTS.items():
    path = BASE / fname
    data = json.loads(path.read_text(encoding='utf-8'))
    n = 0
    for tk, bucket in tickers.items():
        if tk in data:
            data[tk]['bucket'] = bucket
            n += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    json.loads(path.read_text(encoding='utf-8'))
    print(f"{fname[:50]:50s}: assigned bucket on {n} entries")
    total += n
print(f"\nTotal bucket assignments: {total}")
