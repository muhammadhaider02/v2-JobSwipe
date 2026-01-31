"""
Skill extraction from job descriptions using semantic similarity and keyword matching.
Comprehensive taxonomy built from 20 computing roles + soft skills.
"""
import json
import re
from typing import List, Dict, Set
from pathlib import Path
import logging
from sentence_transformers import SentenceTransformer, util
import torch
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SkillExtractor:
    """
    Extract skills from job descriptions using semantic similarity and keyword matching.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the skill extractor.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        logger.info(f"Loading sentence transformer model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.skills_database = self._load_skills_database()
        self.skill_embeddings = None
        self._precompute_embeddings()
        
    def _load_skills_database(self) -> List[str]:
        """Load comprehensive skills database from Excel + additional skills."""
        
        # Load skills from Excel file
        excel_skills = self._load_excel_skills()
        
        # Additional technical skills and variants
        additional_tech_skills = [
            # Programming languages and variants
            "Go", "Golang", "Rust", "Ruby", "PHP", "Perl", "Scala", "Haskell",
            "Julia", "MATLAB", "Assembly", "Bash", "PowerShell", "Shell Scripting",
            
            # Web frameworks and libraries
            "Spring Boot", "Spring Framework", "ASP.NET", "ASP.NET Core",
            "Next.js", "Nuxt.js", "Svelte", "SvelteKit", "jQuery", "Bootstrap",
            "Tailwind CSS", "Material UI", "Chakra UI", "Styled Components",
            
            # Databases and variants
            "MySQL", "SQL Server", "Oracle Database", "MariaDB", "SQLite",
            "Cassandra", "DynamoDB", "Couchbase", "CouchDB", "InfluxDB",
            "TimescaleDB", "Neo4j", "ArangoDB", "Elasticsearch", "Supabase",
            
            # Cloud platforms and services
            "Amazon Web Services", "Microsoft Azure", "Google Cloud Platform",
            "DigitalOcean", "Heroku", "Vercel", "Netlify", "Railway",
            "AWS Lambda", "S3", "EC2", "RDS", "CloudFront", "Route 53",
            "Azure DevOps", "Azure Functions", "Google Cloud Functions",
            
            # DevOps and Infrastructure
            "GitLab CI/CD", "CircleCI", "Travis CI", "Bamboo", "TeamCity",
            "Helm", "ArgoCD", "Istio", "Consul", "Vault", "Nginx", "Apache",
            "HAProxy", "Traefik", "Prometheus", "Grafana", "Datadog",
            "New Relic", "Splunk", "ELK Stack", "Logstash", "Kibana",
            "CloudWatch", "Infrastructure as Code", "Configuration Management",
            
            # Cybersecurity (expanded)
            "Network Security", "Application Security", "Cloud Security",
            "Information Security", "Cyber Defense", "Threat Hunting",
            "Malware Analysis", "Reverse Engineering", "Digital Forensics",
            "Vulnerability Management", "Risk Assessment", "Compliance",
            "Security Operations Center", "SOC", "Threat Intelligence",
            "Security Information and Event Management", "Endpoint Detection",
            "EDR", "XDR", "SOAR", "Zero Trust Architecture",
            "Identity and Access Management", "IAM", "SSO", "MFA",
            "Multi-Factor Authentication", "OAuth", "OAuth 2.0", "OpenID Connect",
            "SAML", "Kerberos", "LDAP", "Active Directory",
            "Public Key Infrastructure", "PKI", "Certificate Management",
            "Encryption", "Cryptography", "TLS", "SSL", "VPN",
            "IPSec", "WireGuard", "Firewall Management", "WAF",
            "Web Application Firewall", "Intrusion Detection System",
            "Intrusion Prevention System", "Network Monitoring",
            "Security Auditing", "Penetration Testing", "Ethical Hacking",
            "Red Team", "Blue Team", "Purple Team", "Bug Bounty",
            "OWASP Top 10", "MITRE ATT&CK", "CIS Controls",
            "ISO 27001", "SOC 2", "NIST Cybersecurity Framework",
            "GDPR", "HIPAA", "PCI DSS", "CCPA",
            "Wireshark", "Nmap", "Metasploit", "Burp Suite", "OWASP ZAP",
            "Nessus", "Qualys", "Rapid7", "Snort", "Suricata",
            "CrowdStrike Falcon", "SentinelOne", "Carbon Black",
            "Palo Alto Networks", "Fortinet", "Check Point", "Cisco ASA",
            "F5", "Imperva", "CloudFlare", "Akamai",
            
            # Data Science and ML (expanded)
            "Data Science", "Data Engineering", "MLOps", "AutoML",
            "Feature Store", "Model Registry", "A/B Testing",
            "Experiment Tracking", "MLflow", "Weights & Biases", "W&B",
            "Kubeflow", "SageMaker", "Azure ML", "Vertex AI",
            "XGBoost", "LightGBM", "CatBoost", "Random Forest",
            "Gradient Boosting", "Support Vector Machines", "SVM",
            "K-Means", "DBSCAN", "Principal Component Analysis", "PCA",
            "t-SNE", "UMAP", "Time Series Analysis", "ARIMA",
            "Prophet", "Forecasting", "Anomaly Detection",
            "Recommendation Systems", "Collaborative Filtering",
            "Natural Language Processing", "Large Language Models", "LLM",
            "GPT", "BERT", "T5", "Llama", "Claude", "Mistral",
            "RAG", "Retrieval Augmented Generation", "Vector Databases",
            "Pinecone", "Weaviate", "Qdrant", "Milvus", "Faiss",
            "LangChain", "LlamaIndex", "Haystack",
            "Computer Vision", "Object Detection", "Image Segmentation",
            "Face Recognition", "OCR", "Image Classification",
            "YOLO", "RCNN", "Mask R-CNN", "U-Net", "ResNet", "VGG",
            "Inception", "EfficientNet", "Vision Transformer", "ViT",
            
            # Mobile and Cross-platform
            "iOS Development", "Android Development", "Mobile Development",
            "SwiftUI", "UIKit", "Jetpack Compose", "Xamarin", "Cordova",
            "Ionic", "Capacitor", "Expo", "React Native", "Flutter",
            
            # Testing and QA
            "Test Automation", "Unit Testing", "Integration Testing",
            "End-to-End Testing", "E2E Testing", "Performance Testing",
            "Load Testing", "Stress Testing", "Security Testing",
            "Penetration Testing", "Regression Testing", "Smoke Testing",
            "JUnit", "TestNG", "pytest", "Jest", "Mocha", "Chai",
            "Jasmine", "Karma", "Cypress", "Playwright", "Puppeteer",
            "Selenium", "WebDriver", "Appium", "Detox", "JMeter",
            "Gatling", "K6", "Locust", "Postman", "Insomnia", "SoapUI",
            
            # API and Integration
            "API Design", "API Development", "RESTful Services",
            "SOAP", "gRPC", "WebSocket", "Server-Sent Events", "SSE",
            "API Gateway", "API Management", "Swagger", "OpenAPI",
            "Postman", "GraphQL", "Apollo", "Hasura", "Prisma",
            
            # Message Queues and Streaming
            "Message Queues", "Message Broker", "Event-Driven Architecture",
            "Apache Kafka", "RabbitMQ", "ActiveMQ", "Amazon SQS", "Azure Service Bus",
            "Google Pub/Sub", "NATS", "ZeroMQ", "Apache Pulsar",
            "Stream Processing", "Apache Flink", "Apache Storm", "Spark Streaming",
            
            # Big Data
            "Big Data", "Hadoop", "Apache Spark", "HDFS", "MapReduce",
            "Hive", "Pig", "HBase", "Cassandra", "Apache Airflow",
            "Luigi", "Prefect", "Dagster", "ETL", "Data Pipeline",
            "Data Warehousing", "Snowflake", "Redshift", "BigQuery",
            
            # Game Development
            "Game Development", "Game Design", "Game Engine",
            "Unity3D", "Unreal Engine 5", "Godot", "Cocos2d",
            "Game Physics", "Shader Programming", "GLSL", "HLSL",
            "DirectX", "OpenGL", "Vulkan", "Metal",
            
            # Blockchain (expanded)
            "Blockchain", "Distributed Ledger", "Smart Contract Development",
            "Web3", "DeFi", "Decentralized Finance", "NFT", "DAO",
            "Ethereum", "Solidity", "Binance Smart Chain", "Polygon",
            "Solana", "Cardano", "Polkadot", "Avalanche", "Near Protocol",
            "Cosmos", "Hyperledger", "Hardhat", "Truffle Suite", "Remix",
            "Ethers.js", "Web3.js", "MetaMask", "WalletConnect",
            
            # AR/VR (expanded)
            "Augmented Reality", "Virtual Reality", "Mixed Reality", "XR",
            "ARKit", "ARCore", "Vuforia", "Wikitude", "Unity AR Foundation",
            "Oculus SDK", "SteamVR", "WebXR", "A-Frame", "Three.js",
            
            # IoT and Embedded
            "Internet of Things", "Embedded Systems", "Firmware Development",
            "Microcontrollers", "Arduino", "Raspberry Pi", "ESP32", "ESP8266",
            "STM32", "PIC", "ARM Cortex", "RTOS", "FreeRTOS", "Zephyr",
            "MQTT", "CoAP", "LoRa", "Zigbee", "BLE", "Bluetooth Low Energy",
            "I2C", "SPI", "UART", "CAN", "Modbus",
            
            # Version Control
            "Version Control", "Source Control", "Git", "GitHub", "GitLab",
            "Bitbucket", "Azure Repos", "SVN", "Mercurial", "Perforce",
            
            # Project Management Tools
            "Jira", "Confluence", "Trello", "Asana", "Monday.com",
            "ClickUp", "Linear", "Notion", "Azure Boards",
            
            # Operating Systems and Linux
            "Linux Administration", "System Administration", "Ubuntu",
            "Debian", "CentOS", "Red Hat Enterprise Linux", "RHEL",
            "Fedora", "Arch Linux", "FreeBSD", "Windows Server",
            "macOS", "Unix", "Shell Scripting", "Bash Scripting",
            "PowerShell Scripting", "Systemd", "Cron", "systemctl",
            
            # Methodologies
            "Agile Methodology", "Scrum", "Kanban", "Lean", "SAFe",
            "Extreme Programming", "XP", "Test-Driven Development", "TDD",
            "Behavior-Driven Development", "BDD", "Domain-Driven Design", "DDD",
            "Microservices Architecture", "Monolithic Architecture",
            "Serverless Architecture", "Event Sourcing", "CQRS",
            "Twelve-Factor App", "Clean Architecture", "Hexagonal Architecture",
            
            # Design and UX
            "UI Design", "UX Design", "User Interface Design",
            "User Experience Design", "Interaction Design", "Visual Design",
            "Graphic Design", "Prototyping", "Wireframing", "Mockups",
            "User Research", "Usability Testing", "A/B Testing",
            "Design Systems", "Figma", "Adobe XD", "Sketch", "InVision",
            "Zeplin", "Framer", "Principle", "Adobe Photoshop",
            "Adobe Illustrator", "Adobe After Effects",
        ]
        
        # Soft skills and professional competencies
        soft_skills = [
            # Communication
            "Communication", "Verbal Communication", "Written Communication",
            "Presentation Skills", "Public Speaking", "Technical Writing",
            "Documentation", "Stakeholder Management", "Client Communication",
            "Cross-functional Communication", "Active Listening",
            
            # Collaboration and Teamwork
            "Teamwork", "Collaboration", "Team Leadership", "Cross-functional Collaboration",
            "Pair Programming", "Code Review", "Peer Feedback", "Mentoring",
            "Knowledge Sharing", "Remote Collaboration",
            
            # Problem Solving and Critical Thinking
            "Problem Solving", "Critical Thinking", "Analytical Thinking",
            "Creative Problem Solving", "Decision Making", "Root Cause Analysis",
            "Troubleshooting", "Debugging", "Systems Thinking", "Strategic Thinking",
            
            # Leadership and Management
            "Leadership", "Team Leadership", "Technical Leadership",
            "Project Management", "Product Management", "People Management",
            "Conflict Resolution", "Delegation", "Coaching", "Motivation",
            
            # Time Management and Organization
            "Time Management", "Task Prioritization", "Organization",
            "Planning", "Resource Management", "Multitasking",
            "Goal Setting", "Deadline Management",
            
            # Adaptability and Learning
            "Adaptability", "Flexibility", "Learning Agility", "Continuous Learning",
            "Self-Learning", "Curiosity", "Innovation", "Creativity",
            "Open-mindedness", "Growth Mindset", "Resilience",
            
            # Work Ethic and Professionalism
            "Work Ethic", "Professionalism", "Reliability", "Accountability",
            "Attention to Detail", "Quality Focus", "Integrity",
            "Self-Motivation", "Initiative", "Ownership",
            
            # Business and Domain Skills
            "Business Acumen", "Domain Knowledge", "Industry Knowledge",
            "Requirements Analysis", "Business Analysis", "Product Thinking",
            "Customer Focus", "User Empathy", "Market Research",
            
            # Specific Professional Skills
            "Estimation", "Planning", "Risk Management", "Change Management",
            "Process Improvement", "Quality Assurance", "Compliance",
            "Vendor Management", "Contract Negotiation", "Budgeting",
        ]
        
        # Combine all skills
        all_skills = list(set(excel_skills + additional_tech_skills + soft_skills))
        
        logger.info(f"Loaded comprehensive skill taxonomy:")
        logger.info(f"  - Excel skills: {len(excel_skills)}")
        logger.info(f"  - Additional technical: {len(additional_tech_skills)}")
        logger.info(f"  - Soft skills: {len(soft_skills)}")
        logger.info(f"  - Total unique: {len(all_skills)}")
        
        return all_skills
    
    def _load_excel_skills(self) -> List[str]:
        """Load skills from the Excel file."""
        try:
            excel_path = Path(__file__).parent / "excel" / "skill_gap.xlsx"
            df = pd.read_excel(excel_path)
            
            skills = set()
            skill_columns = ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5", 
                           "Skill6", "Skill7", "Skill8", "Skill9", "Skill10"]
            
            for col in skill_columns:
                if col in df.columns:
                    col_skills = df[col].dropna().unique().tolist()
                    skills.update(col_skills)
            
            return list(skills)
        except Exception as e:
            logger.warning(f"Could not load Excel skills: {e}")
            return []
    
    def _precompute_embeddings(self):
        """Precompute embeddings for all skills in the database."""
        logger.info("Precomputing skill embeddings...")
        self.skill_embeddings = self.model.encode(
            self.skills_database,
            convert_to_tensor=True,
            show_progress_bar=True
        )
        logger.info(f"Computed embeddings for {len(self.skills_database)} skills")
    
    def extract_skills(
        self,
        job_description: str,
        similarity_threshold: float = 0.5,
        max_skills: int = 30
    ) -> List[Dict[str, any]]:
        """
        Extract skills from a job description.
        
        Args:
            job_description: The job description text
            similarity_threshold: Minimum similarity score (0-1)
            max_skills: Maximum number of skills to return
            
        Returns:
            List of dictionaries with skill name and confidence score
        """
        if not job_description or len(job_description.strip()) < 50:
            logger.warning("Job description too short or empty")
            return []
        
        # Step 1: Exact keyword matching
        exact_matches = self._extract_exact_matches(job_description)
        
        # Step 2: Semantic similarity matching
        semantic_matches = self._extract_semantic_matches(
            job_description,
            similarity_threshold
        )
        
        # Step 3: Combine and deduplicate
        all_skills = self._combine_skills(exact_matches, semantic_matches)
        
        # Step 4: Sort by confidence and limit
        all_skills.sort(key=lambda x: x["confidence"], reverse=True)
        
        return all_skills[:max_skills]
    
    def _extract_exact_matches(self, text: str) -> List[Dict[str, any]]:
        """Extract skills using exact keyword matching."""
        text_lower = text.lower()
        matches = []
        
        for skill in self.skills_database:
            # Create regex pattern for word boundary matching
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            
            if re.search(pattern, text_lower):
                matches.append({
                    "skill": skill,
                    "confidence": 1.0,
                    "method": "exact"
                })
        
        return matches
    
    def _extract_semantic_matches(
        self,
        text: str,
        threshold: float
    ) -> List[Dict[str, any]]:
        """Extract skills using semantic similarity."""
        # Split text into sentences/chunks
        chunks = self._split_into_chunks(text)
        
        if not chunks:
            return []
        
        # Encode chunks
        chunk_embeddings = self.model.encode(
            chunks,
            convert_to_tensor=True,
            show_progress_bar=False
        )
        
        # Compute similarities
        similarities = util.cos_sim(chunk_embeddings, self.skill_embeddings)
        
        # Find high-similarity matches
        matches = []
        matched_skills = set()
        
        for chunk_idx, chunk_sims in enumerate(similarities):
            for skill_idx, sim_score in enumerate(chunk_sims):
                if sim_score >= threshold:
                    skill = self.skills_database[skill_idx]
                    if skill not in matched_skills:
                        matches.append({
                            "skill": skill,
                            "confidence": float(sim_score),
                            "method": "semantic",
                            "context": chunks[chunk_idx][:100]
                        })
                        matched_skills.add(skill)
        
        return matches
    
    def _split_into_chunks(self, text: str, max_length: int = 200) -> List[str]:
        """Split text into smaller chunks for better matching."""
        # Split by sentences (simple approach)
        sentences = re.split(r"[.!?]\s+", text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _combine_skills(
        self,
        exact_matches: List[Dict],
        semantic_matches: List[Dict]
    ) -> List[Dict[str, any]]:
        """Combine and deduplicate skill matches."""
        skill_map = {}
        
        # Add exact matches first (highest priority)
        for match in exact_matches:
            skill_map[match["skill"].lower()] = match
        
        # Add semantic matches if not already present
        for match in semantic_matches:
            skill_lower = match["skill"].lower()
            if skill_lower not in skill_map:
                skill_map[skill_lower] = match
            elif match["confidence"] > skill_map[skill_lower]["confidence"]:
                # Update if semantic match has higher confidence
                skill_map[skill_lower] = match
        
        return list(skill_map.values())


def enrich_metadata_with_skills(
    metadata_path: str,
    similarity_threshold: float = 0.5,
    max_skills: int = 30
):
    """
    Enrich job metadata with extracted skills.
    
    Args:
        metadata_path: Path to the metadata JSON file
        similarity_threshold: Minimum similarity score for semantic matching
        max_skills: Maximum number of skills per job
    """
    logger.info(f"Loading metadata from: {metadata_path}")
    
    # Load metadata
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Initialize skill extractor
    extractor = SkillExtractor()
    
    total_jobs = len(metadata.get("jobs", []))
    processed_count = 0
    skipped_count = 0
    
    logger.info(f"Processing {total_jobs} jobs for skill extraction...")
    
    # Process each job
    for idx, job in enumerate(metadata.get("jobs", []), 1):
        job_title = job.get("title", "Unknown")
        description = job.get("description")
        current_skills = job.get("skills")
        
        logger.info(f"\n[{idx}/{total_jobs}] Processing: {job_title}")
        
        # Skip if skills already exist or no description
        if current_skills is not None and current_skills:
            logger.info(f"Skills already exist, skipping...")
            skipped_count += 1
            continue
        
        if not description or len(description.strip()) < 50:
            logger.warning(f"No valid description found, skipping...")
            skipped_count += 1
            continue
        
        # Extract skills
        logger.info(f"Extracting skills from description ({len(description)} chars)...")
        extracted_skills = extractor.extract_skills(
            description,
            similarity_threshold=similarity_threshold,
            max_skills=max_skills
        )
        
        # Update job with extracted skills
        if extracted_skills:
            # Store as list of skill names
            job["skills"] = [s["skill"] for s in extracted_skills]
            # Optionally store detailed info in a separate field
            job["skills_detailed"] = extracted_skills
            
            processed_count += 1
            logger.info(f" Extracted {len(extracted_skills)} skills")
            logger.info(f"  Top skills: {", ".join([s["skill"] for s in extracted_skills[:5]])}")
        else:
            logger.warning(f" No skills extracted")
    
    # Save updated metadata
    logger.info(f"\nSaving updated metadata...")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{"="*60}")
    logger.info(f"Skill Extraction Complete!")
    logger.info(f"Total jobs: {total_jobs}")
    logger.info(f"Processed: {processed_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Updated file: {metadata_path}")
    logger.info(f"{"="*60}")


if __name__ == "__main__":
    # Path to your metadata file
    metadata_file = r"c:\Users\emaad\Downloads\v2-JobSwipe\backend\scraper\raw_html\demo_user_test\metadata\test_scrape_1769278238_metadata.json"
    
    # Run skill extraction
    enrich_metadata_with_skills(
        metadata_file,
        similarity_threshold=0.5,
        max_skills=30
    )
