"""
Reference lists for the synthetic data generator. All fictional/demo — no real project data.
Deliberately includes Uttar Pradesh per PRD's synthetic data spec (6 states minimum).
"""

# state -> list of districts (kept to ~3-4 per state so total lands near the ~20 district target)
STATE_DISTRICTS = {
    "Uttar Pradesh": ["Lucknow", "Kanpur Nagar", "Varanasi", "Prayagraj"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur"],
    "Maharashtra": ["Pune", "Nagpur", "Nashik"],
    "Tamil Nadu": ["Chennai", "Madurai", "Coimbatore"],
    "West Bengal": ["Kolkata", "Howrah", "Darjeeling"],
    "Rajasthan": ["Jaipur", "Udaipur", "Jodhpur", "Kota"],
}

# Rough lat/long bounding box per state, used to jitter coordinates realistically.
STATE_BOUNDS = {
    "Uttar Pradesh": (25.5, 80.0, 28.5, 83.0),
    "Bihar": (24.5, 84.0, 26.8, 87.5),
    "Maharashtra": (17.0, 73.0, 21.5, 79.5),
    "Tamil Nadu": (8.5, 76.5, 13.0, 80.0),
    "West Bengal": (21.5, 86.5, 27.0, 89.0),
    "Rajasthan": (23.5, 70.0, 29.5, 76.5),
}

WORK_TYPES = [
    "Road Construction",
    "Drinking Water Supply",
    "School Building",
    "Community Hall",
    "Drainage System",
    "Solar Street Lighting",
    "Health Sub-Center",
    "Sports Infrastructure",
    "Irrigation Canal",
    "Public Toilet Complex",
]

# Rough per-unit cost baseline (INR) used to seed realistic peer medians per work type.
WORK_TYPE_BASE_COST = {
    "Road Construction": 4_500_000,
    "Drinking Water Supply": 2_200_000,
    "School Building": 3_800_000,
    "Community Hall": 1_800_000,
    "Drainage System": 2_600_000,
    "Solar Street Lighting": 900_000,
    "Health Sub-Center": 3_200_000,
    "Sports Infrastructure": 2_100_000,
    "Irrigation Canal": 3_500_000,
    "Public Toilet Complex": 700_000,
}

# Generic hyper-local descriptors appended to project titles so that two projects of the same
# work_type in the same district don't collide into an identical title. Without this, a naive
# "{work_type} at {district}" template only has (10 work types x ~20 districts) = 200 possible
# titles across 1,500+ projects, which makes the DUPLICATE_SIMILARITY text detector flag huge
# numbers of unrelated projects as near-identical purely by coincidence -- a data generation
# artifact, not a real duplicate signal. This pool makes accidental title collisions rare enough
# that the deliberately-engineered duplicate_pair hero cases (which force identical titles on
# purpose) remain the clear, distinguishable signal.
TITLE_DESCRIPTORS = [
    "Ward 1", "Ward 2", "Ward 3", "Ward 4", "Ward 5", "Ward 6", "Ward 7", "Ward 8",
    "Sector 3", "Sector 7", "Sector 12", "Sector 15",
    "near Bus Stand", "near Railway Station", "near District Hospital", "near Govt. School",
    "Phase 1", "Phase 2", "Phase 3",
    "Ambedkar Nagar area", "Gandhi Colony area", "Nehru Vihar area", "Shastri Nagar area",
    "Old Town area", "New Colony area", "Industrial Area", "Rural Belt",
    "North Zone", "South Zone", "East Zone", "West Zone",
]

# Description text is built from several independently-randomized phrase pools rather than one
# fixed template. A single fixed template ("{work_type} project under MPLADS in {district}, "
# "{state}.") gives TF-IDF almost no distinguishing vocabulary to work with, since the same
# handful of words repeat across hundreds of projects -- this was found during testing to make
# the DUPLICATE_SIMILARITY detector's text term read 85-95% similarity between completely
# unrelated projects, drowning out the real signal. Combining multiple varied phrase pools gives
# each project's description enough unique vocabulary that only genuinely similar projects (or
# the deliberately-engineered duplicate_pair hero case, which copies the description verbatim)
# score high on text similarity.
DESCRIPTION_SCOPE_PHRASES = [
    "covering approximately {n} households in the target area",
    "aimed at improving basic infrastructure access for local residents",
    "undertaken in response to a community development request",
    "part of a broader area upgrade initiative",
    "prioritized due to population growth in the vicinity",
    "planned in coordination with the local panchayat body",
    "intended to address a long-standing local infrastructure gap",
    "scoped after a site inspection identified urgent need",
    "designed to serve residents across nearby settlements",
    "sanctioned following representations from area residents",
]

DESCRIPTION_BENEFICIARY_PHRASES = [
    "Expected to benefit residents, students, and local businesses.",
    "Local self-help groups were consulted during planning.",
    "Beneficiaries include nearby schools and health facilities.",
    "Community feedback was incorporated into the final scope.",
    "Expected to reduce travel time for daily commuters.",
    "Will support agricultural activity in the surrounding belt.",
    "Aligned with the constituency's annual development priorities.",
    "Coordinated with ongoing works by the state public works department.",
    "Follows an assessment of seasonal usage patterns in the area.",
    "Designed with input from the district planning committee.",
]

AGENCY_SUFFIXES = [
    "Public Works Department", "Rural Development Agency", "Municipal Engineering Cell",
    "Zila Parishad Works Division", "Infrastructure Development Board", "Panchayati Raj Engineering Wing",
]

# Generates ~40 unique fictional agency names by combining district/state with a suffix.
def build_agency_names() -> list[str]:
    names = []
    for state, districts in STATE_DISTRICTS.items():
        for district in districts:
            for suffix in AGENCY_SUFFIXES:
                names.append(f"{district} {suffix}")
    # de-dup and trim to ~40
    seen = list(dict.fromkeys(names))
    return seen[:40]
