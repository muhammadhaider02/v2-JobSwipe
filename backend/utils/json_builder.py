import re

def build_resume_json(entities, raw_text):
    """
    Convert extracted entities into structured JSON format
    """
    resume_data = {
        'personal_info': {},
        'contact': {},
        'experience': [],
        'education': [],
        'skills': [],
        'raw_text': raw_text
    }
    
    # Extract contact information
    if 'emails' in entities and entities['emails']:
        resume_data['contact']['email'] = entities['emails'][0] if entities['emails'] else None
    
    if 'phones' in entities and entities['phones']:
        resume_data['contact']['phone'] = entities['phones'][0] if entities['phones'] else None
    
    # Process NER entities
    if 'ner_entities' in entities:
        persons = []
        organizations = []
        locations = []
        
        for entity in entities['ner_entities']:
            entity_type = entity.get('entity_group', '')
            entity_text = entity.get('word', '')
            
            if entity_type == 'PER':
                persons.append(entity_text)
            elif entity_type == 'ORG':
                organizations.append(entity_text)
            elif entity_type == 'LOC':
                locations.append(entity_text)
        
        # First person mentioned is likely the candidate's name
        if persons:
            resume_data['personal_info']['name'] = persons[0]
        
        # Organizations likely represent work experience or education
        if organizations:
            resume_data['organizations'] = list(set(organizations))
        
        # Locations
        if locations:
            resume_data['locations'] = list(set(locations))
    
    # Extract skills (basic keyword matching)
    resume_data['skills'] = extract_skills(raw_text)
    
    # Extract education keywords
    resume_data['education'] = extract_education(raw_text)
    
    return resume_data

def extract_skills(text):
    """
    Extract common technical skills from text
    """
    common_skills = [
        'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'swift',
        'sql', 'html', 'css', 'react', 'angular', 'vue', 'node.js', 'django',
        'flask', 'spring', 'docker', 'kubernetes', 'aws', 'azure', 'gcp',
        'machine learning', 'deep learning', 'ai', 'data science', 'tensorflow',
        'pytorch', 'git', 'agile', 'scrum', 'rest api', 'graphql'
    ]
    
    text_lower = text.lower()
    found_skills = []
    
    for skill in common_skills:
        if skill in text_lower:
            found_skills.append(skill)
    
    return found_skills

def extract_education(text):
    """
    Extract education-related information
    """
    education_keywords = [
        'bachelor', 'master', 'phd', 'doctorate', 'mba', 'b.s.', 'b.a.',
        'm.s.', 'm.a.', 'university', 'college', 'institute', 'degree'
    ]
    
    text_lower = text.lower()
    education_info = []
    
    for keyword in education_keywords:
        if keyword in text_lower:
            # Find sentences containing education keywords
            sentences = re.split(r'[.!?\n]', text)
            for sentence in sentences:
                if keyword in sentence.lower() and sentence.strip():
                    education_info.append(sentence.strip())
    
    return list(set(education_info))
