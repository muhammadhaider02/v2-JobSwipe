"""
Taxonomy Service - Hardcoded Core Skill Taxonomy
Maintains 20+ major skills with curated subskills and aliases for skill normalization
"""
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


class TaxonomyService:
    """Service for managing hardcoded core skill taxonomy"""
    
    # Core Skill Taxonomy - Top 20+ Skills with Subskills and Aliases
    CORE_TAXONOMY: Dict[str, Dict[str, any]] = {
        "python": {
            "canonical_name": "Python",
            "db_table": "Backend Developer",  # Maps to quiz.db table
            "subskills": [
                "Syntax", "Data Types", "Control Flow", "Functions", 
                "OOP", "Modules", "Exception Handling", "File I/O",
                "List Comprehensions", "Decorators", "Generators"
            ],
            "aliases": [
                "python3", "python developer", "backend python", 
                "python programming", "python scripting", "py"
            ]
        },
        "javascript": {
            "canonical_name": "JavaScript",
            "db_table": "Frontend Developer",
            "subskills": [
                "ES6+", "Async/Await", "Promises", "DOM Manipulation",
                "Event Handling", "Closures", "Prototypes", "Arrow Functions",
                "Template Literals", "Destructuring"
            ],
            "aliases": [
                "js", "javascript developer", "frontend javascript",
                "node.js", "nodejs", "ecmascript"
            ]
        },
        "react": {
            "canonical_name": "React",
            "db_table": "Frontend Developer",
            "subskills": [
                "JSX", "Components", "Props", "State Management",
                "Hooks", "useEffect", "useState", "Context API",
                "Component Lifecycle", "Virtual DOM", "React Router"
            ],
            "aliases": [
                "reactjs", "react.js", "react developer", "react native",
                "frontend react"
            ]
        },
        "machine learning": {
            "canonical_name": "Machine Learning",
            "db_table": "ML Engineer",
            "subskills": [
                "Supervised Learning", "Unsupervised Learning", 
                "Feature Engineering", "Model Evaluation", "Cross-Validation",
                "Regression", "Classification", "Clustering", "Neural Networks",
                "Overfitting Prevention", "Hyperparameter Tuning"
            ],
            "aliases": [
                "ml", "ml engineer", "machine learning engineer",
                "machine learning developer", "ml developer"
            ]
        },
        "deep learning": {
            "canonical_name": "Deep Learning",
            "db_table": "ML Engineer",
            "subskills": [
                "Neural Networks", "CNN", "RNN", "LSTM", "Transformers",
                "Backpropagation", "Activation Functions", "Loss Functions",
                "Gradient Descent", "Transfer Learning", "Fine-tuning"
            ],
            "aliases": [
                "dl", "deep neural networks", "dnn", "artificial neural networks"
            ]
        },
        "artificial intelligence": {
            "canonical_name": "Artificial Intelligence",
            "db_table": "AI Engineer",
            "subskills": [
                "Search Algorithms", "Knowledge Representation",
                "Expert Systems", "Natural Language Processing",
                "Computer Vision", "Planning", "Reasoning",
                "Machine Learning", "Neural Networks"
            ],
            "aliases": [
                "ai", "ai engineer", "ai developer", "artificial intelligence engineer"
            ]
        },
        "data science": {
            "canonical_name": "Data Science",
            "db_table": "Data Scientist",
            "subskills": [
                "Data Analysis", "Statistical Modeling", "Data Visualization",
                "Pandas", "NumPy", "Matplotlib", "Seaborn", "Statistics",
                "Hypothesis Testing", "A/B Testing", "Feature Engineering"
            ],
            "aliases": [
                "data scientist", "data science engineer", "ds"
            ]
        },
        "data analysis": {
            "canonical_name": "Data Analysis",
            "db_table": "Data Analyst",
            "subskills": [
                "SQL", "Excel", "Data Cleaning", "Data Visualization",
                "Business Intelligence", "Reporting", "Dashboard Creation",
                "Pivot Tables", "Data Mining", "Statistical Analysis"
            ],
            "aliases": [
                "data analyst", "business analyst", "bi analyst",
                "business intelligence", "data analytics"
            ]
        },
        "devops": {
            "canonical_name": "DevOps",
            "db_table": "DevOps Engineer",
            "subskills": [
                "CI/CD", "Docker", "Kubernetes", "Jenkins",
                "Infrastructure as Code", "Terraform", "Ansible",
                "Monitoring", "Logging", "Git", "Pipeline Automation"
            ],
            "aliases": [
                "devops engineer", "site reliability engineer", "sre",
                "platform engineer", "ci/cd engineer"
            ]
        },
        "cloud computing": {
            "canonical_name": "Cloud Computing",
            "db_table": "Cloud Engineer",
            "subskills": [
                "AWS", "Azure", "Google Cloud", "EC2", "S3",
                "Lambda", "Cloud Storage", "Networking", "IAM",
                "Load Balancing", "Auto Scaling", "Cloud Security"
            ],
            "aliases": [
                "cloud", "cloud engineer", "aws", "azure", "gcp",
                "aws engineer", "azure engineer", "gcp engineer"
            ]
        },
        "cybersecurity": {
            "canonical_name": "Cybersecurity",
            "db_table": "Cybersecurity Engineer",
            "subskills": [
                "Network Security", "Encryption", "Penetration Testing",
                "Vulnerability Assessment", "Firewalls", "Intrusion Detection",
                "Security Auditing", "Ethical Hacking", "Threat Analysis"
            ],
            "aliases": [
                "security", "information security", "infosec",
                "cybersecurity engineer", "security engineer", "ethical hacking"
            ]
        },
        "full stack development": {
            "canonical_name": "Full Stack Development",
            "db_table": "Full Stack Developer",
            "subskills": [
                "Frontend", "Backend", "Databases", "REST APIs",
                "Authentication", "Deployment", "Version Control",
                "Responsive Design", "Server Management", "API Integration"
            ],
            "aliases": [
                "full stack", "fullstack", "full-stack developer",
                "fullstack developer", "full stack engineer"
            ]
        },
        "frontend development": {
            "canonical_name": "Frontend Development",
            "db_table": "Frontend Developer",
            "subskills": [
                "HTML", "CSS", "JavaScript", "Responsive Design",
                "CSS Grid", "Flexbox", "DOM Manipulation",
                "Web Accessibility", "Browser DevTools", "Performance Optimization"
            ],
            "aliases": [
                "frontend", "front-end", "front end developer",
                "frontend developer", "ui developer", "web developer"
            ]
        },
        "backend development": {
            "canonical_name": "Backend Development",
            "db_table": "Backend Developer",
            "subskills": [
                "REST APIs", "Database Design", "Authentication",
                "Authorization", "Server Architecture", "Caching",
                "Message Queues", "Microservices", "API Security"
            ],
            "aliases": [
                "backend", "back-end", "backend developer",
                "back-end developer", "server-side developer"
            ]
        },
        "mobile development": {
            "canonical_name": "Mobile Development",
            "db_table": "Mobile App Developer",
            "subskills": [
                "iOS Development", "Android Development",
                "React Native", "Flutter", "Mobile UI/UX",
                "App Store Deployment", "Push Notifications",
                "Mobile Performance", "Offline Storage"
            ],
            "aliases": [
                "mobile", "mobile developer", "app developer",
                "android developer", "ios developer", "mobile app developer"
            ]
        },
        "game development": {
            "canonical_name": "Game Development",
            "db_table": "Game Developer",
            "subskills": [
                "Unity", "Unreal Engine", "Game Physics",
                "3D Graphics", "Game Design", "Animation",
                "Collision Detection", "AI for Games", "Shader Programming"
            ],
            "aliases": [
                "game dev", "game developer", "unity developer",
                "unreal developer", "game programmer"
            ]
        },
        "ui/ux design": {
            "canonical_name": "UI/UX Design",
            "db_table": "UI/UX Designer",
            "subskills": [
                "User Research", "Wireframing", "Prototyping",
                "Figma", "Adobe XD", "User Testing",
                "Information Architecture", "Design Systems",
                "Interaction Design", "Usability Testing"
            ],
            "aliases": [
                "ui", "ux", "ui designer", "ux designer",
                "product designer", "user experience", "user interface"
            ]
        },
        "computer vision": {
            "canonical_name": "Computer Vision",
            "db_table": "Computer Vision Engineer",
            "subskills": [
                "Image Processing", "Object Detection",
                "Image Classification", "OpenCV", "CNNs",
                "Image Segmentation", "Feature Extraction",
                "Face Recognition", "OCR", "Video Processing"
            ],
            "aliases": [
                "cv", "computer vision engineer", "cv engineer",
                "image processing", "vision ai"
            ]
        },
        "natural language processing": {
            "canonical_name": "Natural Language Processing",
            "db_table": "NLP Engineer",
            "subskills": [
                "Text Processing", "Tokenization", "NER",
                "Sentiment Analysis", "Language Models",
                "Text Classification", "Word Embeddings",
                "Transformers", "BERT", "GPT", "Seq2Seq"
            ],
            "aliases": [
                "nlp", "nlp engineer", "text processing",
                "text analytics", "language ai"
            ]
        },
        "blockchain": {
            "canonical_name": "Blockchain",
            "db_table": "Blockchain Developer",
            "subskills": [
                "Smart Contracts", "Solidity", "Ethereum",
                "Web3", "DApps", "Cryptography",
                "Consensus Algorithms", "Blockchain Architecture",
                "Token Standards", "DeFi"
            ],
            "aliases": [
                "blockchain developer", "web3", "web3 developer",
                "ethereum developer", "solidity developer", "crypto developer"
            ]
        },
        "database": {
            "canonical_name": "Database",
            "db_table": "Backend Developer",
            "subskills": [
                "SQL", "NoSQL", "Database Design", "Indexing",
                "Query Optimization", "Normalization", "Transactions",
                "MongoDB", "PostgreSQL", "MySQL", "Redis"
            ],
            "aliases": [
                "database developer", "dba", "database administrator",
                "sql developer", "database engineer"
            ]
        },
        "embedded systems": {
            "canonical_name": "Embedded Systems",
            "db_table": "Embedded Systems Engineer",
            "subskills": [
                "C Programming", "Microcontrollers", "RTOS",
                "Embedded C", "Hardware Interfaces", "IoT",
                "Firmware Development", "Sensor Integration",
                "Low-Level Programming", "Arduino", "Raspberry Pi"
            ],
            "aliases": [
                "embedded", "embedded developer", "iot developer",
                "firmware developer", "embedded engineer"
            ]
        },
        "ar/vr": {
            "canonical_name": "AR/VR Development",
            "db_table": "AR_VR_Developer",
            "subskills": [
                "Unity 3D", "Unreal Engine", "3D Modeling",
                "Spatial Computing", "VR Interaction Design",
                "AR Kit", "AR Core", "Mixed Reality",
                "Virtual Reality", "Augmented Reality"
            ],
            "aliases": [
                "ar", "vr", "ar developer", "vr developer",
                "augmented reality", "virtual reality", "xr developer"
            ]
        },
        "statistics": {
            "canonical_name": "Statistics",
            "db_table": "Data Analyst",  # Maps to Data Analyst table in quiz.db
            "subskills": [
                "Descriptive Statistics", "Inferential Statistics",
                "Probability", "Hypothesis Testing", "Regression Analysis",
                "ANOVA", "Chi-Square Tests", "Correlation",
                "Standard Deviation", "Confidence Intervals",
                "P-Values", "Normal Distribution", "T-Tests"
            ],
            "aliases": [
                "stats", "statistical analysis", "data statistics",
                "statistics and probability", "statistical methods",
                "biostatistics", "applied statistics"
            ]
        }
    }
    
    def __init__(self):
        """Initialize taxonomy service"""
        self._build_reverse_index()
        print(f"✓ TaxonomyService initialized with {len(self.CORE_TAXONOMY)} core skills")
    
    def _build_reverse_index(self):
        """Build reverse index for fast alias lookup"""
        self.alias_to_canonical = {}
        
        for canonical_key, data in self.CORE_TAXONOMY.items():
            # Map canonical name itself
            self.alias_to_canonical[canonical_key.lower()] = canonical_key
            self.alias_to_canonical[data["canonical_name"].lower()] = canonical_key
            
            # Map all aliases
            for alias in data["aliases"]:
                self.alias_to_canonical[alias.lower()] = canonical_key
    
    def normalize_skill(self, skill: str) -> Optional[str]:
        """
        Normalize a skill name to its canonical form.
        
        Args:
            skill: Raw skill name (e.g., "python3", "ml engineer")
            
        Returns:
            Canonical skill key (e.g., "python", "machine learning") or None
        """
        skill_lower = skill.lower().strip()
        
        # Direct lookup in alias index
        canonical = self.alias_to_canonical.get(skill_lower)
        if canonical:
            return canonical
        
        return None
    
    def get_skill_data(self, canonical_skill: str) -> Optional[Dict]:
        """
        Get complete skill data for a canonical skill.
        
        Args:
            canonical_skill: Canonical skill key
            
        Returns:
            Skill data dict or None
        """
        return self.CORE_TAXONOMY.get(canonical_skill)
    
    def get_subskills(self, canonical_skill: str) -> List[str]:
        """Get subskills for a canonical skill"""
        skill_data = self.get_skill_data(canonical_skill)
        return skill_data["subskills"] if skill_data else []
    
    def get_db_table(self, canonical_skill: str) -> Optional[str]:
        """Get database table name for a canonical skill"""
        skill_data = self.get_skill_data(canonical_skill)
        return skill_data["db_table"] if skill_data else None
    
    def fuzzy_match(self, skill: str, threshold: float = 0.6) -> Tuple[Optional[str], float]:
        """
        Find best fuzzy match for a skill against taxonomy.
        
        Args:
            skill: Input skill name
            threshold: Minimum similarity threshold (0.0 - 1.0)
            
        Returns:
            Tuple of (canonical_skill, similarity_score)
        """
        skill_lower = skill.lower().strip()
        best_match = None
        best_score = 0.0
        
        # Check all canonical names and aliases
        for search_term, canonical in self.alias_to_canonical.items():
            # Calculate base similarity
            similarity = SequenceMatcher(None, skill_lower, search_term).ratio()
            
            # Boost for substring matches
            if skill_lower in search_term or search_term in skill_lower:
                similarity = max(similarity, 0.75)
            
            # Boost for word overlap
            skill_words = set(skill_lower.split())
            term_words = set(search_term.split())
            if skill_words and term_words:
                word_overlap = len(skill_words & term_words) / len(skill_words | term_words)
                similarity = max(similarity, word_overlap)
            
            if similarity > best_score:
                best_score = similarity
                best_match = canonical
        
        # Only return match if above threshold
        if best_score >= threshold:
            return best_match, best_score
        
        return None, 0.0
    
    def get_all_skills(self) -> List[Dict[str, any]]:
        """Get list of all skills in taxonomy"""
        skills = []
        for key, data in self.CORE_TAXONOMY.items():
            skills.append({
                "key": key,
                "name": data["canonical_name"],
                "subskills": data["subskills"],
                "aliases": data["aliases"],
                "db_table": data["db_table"]
            })
        return skills
    
    def resolve_to_db_table(self, skill: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Resolve a skill to its database table using taxonomy.
        
        Args:
            skill: Input skill name
            
        Returns:
            Tuple of (db_table, canonical_skill, match_type)
            match_type: "exact", "fuzzy", or "none"
        """
        # Try exact match first
        canonical = self.normalize_skill(skill)
        if canonical:
            db_table = self.get_db_table(canonical)
            return db_table, canonical, "exact"
        
        # Try fuzzy match
        canonical, score = self.fuzzy_match(skill, threshold=0.6)
        if canonical:
            db_table = self.get_db_table(canonical)
            return db_table, canonical, "fuzzy"
        
        # No match
        return None, None, "none"
