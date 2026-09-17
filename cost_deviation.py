"""
COST_DEVIATION detector. Weight: 20%.
Skipped entirely (never fabricated) if no peer group reaches the minimum sample size --
this is what "rebalance over available factors" means in the scoring formula.
"""
from app.services.peer_stats import PeerStats


def compute_cost_deviation(project_cost: float, peer: PeerStats) -> dict:
    deviation_percent = (project_cost - peer.median_cost) / max(peer.median_cost, 1) * 100
    normalized_score = min(100.0, max(0.0, deviation_percent))

    explanation = (
        f"Project cost is {deviation_percent:.1f}% {'above' if deviation_percent >= 0 else 'below'} "
        f"the peer median of Rs {peer.median_cost:,.0f}, based on {peer.sample_count} comparable "
        f"{peer.group_level}-level projects."
    )
    evidence = {
        "project_cost": project_cost,
        "peer_median_cost": peer.median_cost,
        "peer_iqr_low": peer.iqr_low,
        "peer_iqr_high": peer.iqr_high,
        "peer_sample_count": peer.sample_count,
        "peer_group_level": peer.group_level,
        "peer_group_value": peer.group_value,
        "deviation_percent": round(deviation_percent, 2),
    }
    return {
        "raw_value": round(deviation_percent, 2),
        "normalized_score": round(normalized_score, 2),
        "evidence": evidence,
        "explanation": explanation,
    }
