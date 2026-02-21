"""
Domain trust scoring for ranking search results.
Higher scores indicate more authoritative educational sources.
"""
from typing import Dict
import re


# Trusted educational domains with authority scores (0.0 to 1.0)
DOMAIN_TRUST_SCORES: Dict[str, float] = {
    # Academic institutions
    "mit.edu": 1.0,
    "stanford.edu": 1.0,
    "harvard.edu": 1.0,
    "berkeley.edu": 1.0,
    "ox.ac.uk": 1.0,
    "cambridge.org": 1.0,
    
    # Major learning platforms
    "coursera.org": 0.95,
    "edx.org": 0.95,
    "udacity.com": 0.95,
    "khanacademy.org": 0.95,
    
    # Documentation & tutorials
    "python.org": 0.95,
    "docs.python.org": 0.95,
    "developer.mozilla.org": 0.95,
    "w3schools.com": 0.85,
    "geeksforgeeks.org": 0.8,
    "tutorialspoint.com": 0.75,
    
    # Quality content platforms
    "freecodecamp.org": 0.9,
    "realpython.com": 0.9,
    "medium.com": 0.7,
    "dev.to": 0.7,
    "towardsdatascience.com": 0.8,
    
    # Tech company docs
    "developers.google.com": 0.9,
    "docs.microsoft.com": 0.9,
    "aws.amazon.com": 0.9,
    "cloud.google.com": 0.9,
    
    # Community platforms
    "stackoverflow.com": 0.85,
    "github.com": 0.8,
    "reddit.com": 0.6,
}

# YouTube channel trust scores
CHANNEL_TRUST_SCORES: Dict[str, float] = {
    # Educational channels
    "cs50": 1.0,
    "freecodecamp.org": 0.95,
    "freecodecamporg": 0.95,
    "mit opencourseware": 0.95,
    "stanford online": 0.95,
    "corey schafer": 0.9,
    "traversy media": 0.9,
    "programming with mosh": 0.9,
    "sentdex": 0.85,
    "tech with tim": 0.85,
    "the net ninja": 0.85,
    "academind": 0.85,
    "fireship": 0.85,
    "web dev simplified": 0.85,
    "code with harry": 0.8,
    "programming knowledge": 0.8,
}

# Non-tech domains to filter out (e.g., medical, beauty, sports stats)
NON_TECH_DOMAINS = [
    "health", "medical", "healthcare", "medicine", "hospital",
    "beauty", "cosmetics", "makeup", "salon", "spa",
    "sports", "fitness", "athletics", "gym", "workout",
    "cooking", "recipe", "food", "restaurant", "culinary",
    "fashion", "clothing", "apparel", "style",
    "real-estate", "property", "housing",
    "insurance", "finance.yahoo", "investing.com",
    "travel", "tourism", "hotel",
    "legal", "law", "attorney", "lawyer",
]

# Tech-relevant domain indicators (boost these)
TECH_DOMAIN_INDICATORS = [
    "tech", "dev", "code", "programming", "software", "computer",
    "data", "analytics", "science", "engineering", "developer",
    "digital", "web", "api", "cloud", "database", "algorithm",
    "machine-learning", "ai", "cybersecurity", "blockchain",
    "statistics", "statistical", "python", "r programming", "sql",
    "visualization", "analysis", "machine learning", "deep learning",
    "tutorial", "course", "learn", "guide", "documentation"
]


def get_domain_trust_score(url: str) -> float:
    """
    Calculate trust score for a domain.
    
    Args:
        url: Full URL of the resource
        
    Returns:
        Trust score between 0.0 and 1.0
    """
    # Extract domain from URL
    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    if not domain_match:
        return 0.5  # Default neutral score
    
    domain = domain_match.group(1).lower()
    
    # Check exact match
    if domain in DOMAIN_TRUST_SCORES:
        return DOMAIN_TRUST_SCORES[domain]
    
    # Check if it's an educational domain (.edu)
    if domain.endswith('.edu'):
        return 0.9
    
    # Check if it's an academic domain (.ac.uk, .ac.in, etc.)
    if '.ac.' in domain:
        return 0.85
    
    # Check partial matches for known domains
    for trusted_domain, score in DOMAIN_TRUST_SCORES.items():
        if trusted_domain in domain:
            return score * 0.9  # Slightly lower for subdomain matches
    
    # Default score for unknown domains
    return 0.5


def get_channel_trust_score(channel_name: str) -> float:
    """
    Calculate trust score for a YouTube channel.
    
    Args:
        channel_name: Name of the YouTube channel
        
    Returns:
        Trust score between 0.0 and 1.0
    """
    channel_lower = channel_name.lower().strip()
    
    # Check exact match
    if channel_lower in CHANNEL_TRUST_SCORES:
        return CHANNEL_TRUST_SCORES[channel_lower]
    
    # Check partial matches
    for trusted_channel, score in CHANNEL_TRUST_SCORES.items():
        if trusted_channel in channel_lower or channel_lower in trusted_channel:
            return score * 0.95
    
    # Default score for unknown channels
    return 0.6


def is_blacklisted_domain(url: str) -> bool:
    """
    Check if a domain should be filtered out.
    
    Args:
        url: Full URL to check
        
    Returns:
        True if domain is blacklisted
    """
    blacklisted = [
        'ads.',
        'ad.',
        'sponsored',
        'promo',
        'affiliate',
        'clickbank',
    ]
    
    url_lower = url.lower()
    return any(blocked in url_lower for blocked in blacklisted)


def is_non_tech_domain(url: str) -> bool:
    """
    Check if a domain is from a non-tech industry (medical, beauty, sports, etc.).
    
    Args:
        url: Full URL to check
        
    Returns:
        True if domain is non-tech and should be filtered
    """
    url_lower = url.lower()
    
    # Check against non-tech domain list
    for non_tech in NON_TECH_DOMAINS:
        if non_tech in url_lower:
            return True
    
    return False


def is_tech_relevant_domain(url: str, title: str = "", snippet: str = "") -> bool:
    """
    Check if a domain/content is tech-relevant.
    
    Args:
        url: Full URL to check
        title: Page title
        snippet: Page description/snippet
        
    Returns:
        True if content appears tech-relevant
    """
    # Combine all text for analysis
    combined_text = f"{url} {title} {snippet}".lower()
    
    # Check for tech indicators
    tech_score = sum(1 for indicator in TECH_DOMAIN_INDICATORS if indicator in combined_text)
    
    # Check for non-tech indicators
    non_tech_score = sum(1 for indicator in NON_TECH_DOMAINS if indicator in combined_text)
    
    # If we have strong non-tech indicators (2+), filter it out
    if non_tech_score >= 2:
        return False
    
    # If we have any tech indicators, it's relevant
    if tech_score >= 1:
        return True
    
    # If we have 1 non-tech indicator but it's from a trusted domain, allow it
    # (e.g., w3schools might have "learn" which is fine)
    if non_tech_score == 1:
        # Check if it's from a trusted educational domain
        for trusted_domain in DOMAIN_TRUST_SCORES.keys():
            if trusted_domain in url.lower():
                return True
    
    # Default: be permissive (assume relevant unless proven otherwise)
    # This prevents filtering out good results that just don't have specific keywords
    return non_tech_score == 0
