from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import re

class NERModel:
    def __init__(self, model_name="dslim/bert-base-NER"):
        """
        Initialize the NER model using Hugging Face transformers
        Default model: dslim/bert-base-NER (recognizes PER, ORG, LOC, MISC)
        """
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForTokenClassification.from_pretrained(model_name)
            self.ner_pipeline = pipeline(
                "ner",
                model=self.model,
                tokenizer=self.tokenizer,
                aggregation_strategy="simple"
            )
        except Exception as e:
            print(f"Error loading model: {e}")
            self.ner_pipeline = None
    
    def extract_entities(self, text):
        """
        Extract named entities from text
        Returns a list of entities with their labels and positions
        """
        if not self.ner_pipeline:
            return []
        
        try:
            # Run NER pipeline
            entities = self.ner_pipeline(text)
            
            # Additional resume-specific extraction
            emails = self._extract_emails(text)
            phones = self._extract_phone_numbers(text)
            
            # Combine all entities
            all_entities = {
                'ner_entities': entities,
                'emails': emails,
                'phones': phones
            }
            
            return all_entities
        
        except Exception as e:
            print(f"Error extracting entities: {e}")
            return {}
    
    def _extract_emails(self, text):
        """Extract email addresses using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    def _extract_phone_numbers(self, text):
        """Extract phone numbers using regex"""
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, text))
        
        return list(set(phones))  # Remove duplicates
