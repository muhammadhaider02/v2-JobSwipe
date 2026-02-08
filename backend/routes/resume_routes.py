from flask import Blueprint, request, jsonify, send_file
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
import logging
from datetime import datetime

resume_bp = Blueprint('resume', __name__)
logger = logging.getLogger(__name__)

def create_modern_template(profile_data, buffer):
    """Modern Pro template with blue accent colors"""
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                          topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.75*inch, rightMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=6,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=12,
        borderWidth=1,
        borderColor=colors.HexColor('#2563eb'),
        borderPadding=5
    )
    
    # Name
    story.append(Paragraph(profile_data['name'], title_style))
    
    # Contact info
    contact_parts = []
    if profile_data.get('email'):
        contact_parts.append(profile_data['email'])
    if profile_data.get('phone'):
        contact_parts.append(profile_data['phone'])
    if profile_data.get('location'):
        contact_parts.append(profile_data['location'])
    
    if contact_parts:
        contact_text = ' • '.join(contact_parts)
        story.append(Paragraph(contact_text, ParagraphStyle('Contact', parent=styles['Normal'], 
                                                            alignment=TA_CENTER, fontSize=10)))
    
    # Links
    links = []
    if profile_data.get('linkedin'):
        links.append('LinkedIn')
    if profile_data.get('github'):
        links.append('GitHub')
    if profile_data.get('portfolio'):
        links.append('Portfolio')
    
    if links:
        story.append(Paragraph(' • '.join(links), ParagraphStyle('Links', parent=styles['Normal'], 
                                                                 alignment=TA_CENTER, fontSize=9)))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Summary
    if profile_data.get('summary'):
        story.append(Paragraph('PROFESSIONAL SUMMARY', header_style))
        story.append(Paragraph(profile_data['summary'], styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Skills
    if profile_data.get('skills') and len(profile_data['skills']) > 0:
        story.append(Paragraph('SKILLS', header_style))
        skills_text = ' • '.join(profile_data['skills'])
        story.append(Paragraph(skills_text, styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Experience
    if profile_data.get('experience') and len(profile_data['experience']) > 0:
        exp_list = [exp for exp in profile_data['experience'] if exp.get('company')]
        if exp_list:
            story.append(Paragraph('EXPERIENCE', header_style))
            for exp in exp_list:
                job_title = f"<b>{exp.get('role', '')}</b>"
                story.append(Paragraph(job_title, styles['Normal']))
                
                company_duration = exp.get('company', '')
                if exp.get('duration'):
                    company_duration += f" • {exp['duration']}"
                story.append(Paragraph(company_duration, ParagraphStyle('Company', parent=styles['Normal'], 
                                                                        fontSize=10, textColor=colors.grey)))
                
                if exp.get('description'):
                    story.append(Paragraph(exp['description'], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Education
    if profile_data.get('education') and len(profile_data['education']) > 0:
        edu_list = [edu for edu in profile_data['education'] if edu.get('degree')]
        if edu_list:
            story.append(Paragraph('EDUCATION', header_style))
            for edu in edu_list:
                degree = f"<b>{edu.get('degree', '')}</b>"
                story.append(Paragraph(degree, styles['Normal']))
                
                institution_parts = [edu.get('institution', '')]
                if edu.get('startYear') or edu.get('endYear'):
                    year_range = f"{edu.get('startYear', '')} - {edu.get('endYear', '')}"
                    institution_parts.append(year_range)
                if edu.get('gpa'):
                    institution_parts.append(f"GPA: {edu['gpa']}")
                
                institution_text = ' • '.join([p for p in institution_parts if p])
                story.append(Paragraph(institution_text, ParagraphStyle('Institution', parent=styles['Normal'], 
                                                                       fontSize=10, textColor=colors.grey)))
                story.append(Spacer(1, 0.1*inch))
    
    # Projects
    if profile_data.get('projects') and len(profile_data['projects']) > 0:
        proj_list = [proj for proj in profile_data['projects'] if proj.get('name')]
        if proj_list:
            story.append(Paragraph('PROJECTS', header_style))
            for proj in proj_list:
                project_name = f"<b>{proj.get('name', '')}</b>"
                story.append(Paragraph(project_name, styles['Normal']))
                if proj.get('description'):
                    story.append(Paragraph(proj['description'], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Certifications
    if profile_data.get('certificates') and len(profile_data['certificates']) > 0:
        cert_list = [cert for cert in profile_data['certificates'] if cert.get('name')]
        if cert_list:
            story.append(Paragraph('CERTIFICATIONS', header_style))
            for cert in cert_list:
                cert_name = f"<b>{cert.get('name', '')}</b>"
                story.append(Paragraph(cert_name, styles['Normal']))
                
                cert_info = cert.get('issuer', '')
                if cert.get('issueDate'):
                    try:
                        issue_date = datetime.fromisoformat(cert['issueDate'].replace('Z', '+00:00'))
                        cert_info += f" • {issue_date.strftime('%B %Y')}"
                    except:
                        pass
                
                if cert_info:
                    story.append(Paragraph(cert_info, ParagraphStyle('CertInfo', parent=styles['Normal'], 
                                                                     fontSize=10, textColor=colors.grey)))
                story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    return buffer

def create_classic_template(profile_data, buffer):
    """Classic Formal template with traditional layout"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.75*inch, rightMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.black,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderPadding=0,
        underlineWidth=1
    )
    
    # Name
    story.append(Paragraph(profile_data['name'].upper(), title_style))
    
    # Contact info
    contact_parts = []
    if profile_data.get('email'):
        contact_parts.append(profile_data['email'])
    if profile_data.get('phone'):
        contact_parts.append(profile_data['phone'])
    if profile_data.get('location'):
        contact_parts.append(profile_data['location'])
    
    if contact_parts:
        contact_text = ' | '.join(contact_parts)
        story.append(Paragraph(contact_text, ParagraphStyle('Contact', parent=styles['Normal'], 
                                                            alignment=TA_CENTER, fontSize=9)))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Summary
    if profile_data.get('summary'):
        story.append(Paragraph('SUMMARY', header_style))
        story.append(Paragraph(profile_data['summary'], styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Experience
    if profile_data.get('experience') and len(profile_data['experience']) > 0:
        exp_list = [exp for exp in profile_data['experience'] if exp.get('company')]
        if exp_list:
            story.append(Paragraph('PROFESSIONAL EXPERIENCE', header_style))
            for exp in exp_list:
                job_title = f"<b>{exp.get('role', '')}</b>"
                story.append(Paragraph(job_title, styles['Normal']))
                
                company_duration = exp.get('company', '')
                if exp.get('duration'):
                    company_duration += f" ({exp['duration']})"
                story.append(Paragraph(company_duration, styles['Normal']))
                
                if exp.get('description'):
                    story.append(Paragraph(f"• {exp['description']}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Education
    if profile_data.get('education') and len(profile_data['education']) > 0:
        edu_list = [edu for edu in profile_data['education'] if edu.get('degree')]
        if edu_list:
            story.append(Paragraph('EDUCATION', header_style))
            for edu in edu_list:
                degree = f"<b>{edu.get('degree', '')}</b>"
                story.append(Paragraph(degree, styles['Normal']))
                
                institution = edu.get('institution', '')
                story.append(Paragraph(institution, styles['Normal']))
                
                if edu.get('startYear') or edu.get('endYear'):
                    year_range = f"{edu.get('startYear', '')} - {edu.get('endYear', '')}"
                    if edu.get('gpa'):
                        year_range += f" | GPA: {edu['gpa']}"
                    story.append(Paragraph(year_range, styles['Normal']))
                
                story.append(Spacer(1, 0.1*inch))
    
    # Skills
    if profile_data.get('skills') and len(profile_data['skills']) > 0:
        story.append(Paragraph('SKILLS', header_style))
        skills_text = ', '.join(profile_data['skills'])
        story.append(Paragraph(skills_text, styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Projects
    if profile_data.get('projects') and len(profile_data['projects']) > 0:
        proj_list = [proj for proj in profile_data['projects'] if proj.get('name')]
        if proj_list:
            story.append(Paragraph('PROJECTS', header_style))
            for proj in proj_list:
                project_name = f"<b>{proj.get('name', '')}</b>"
                story.append(Paragraph(project_name, styles['Normal']))
                if proj.get('description'):
                    story.append(Paragraph(proj['description'], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Certifications
    if profile_data.get('certificates') and len(profile_data['certificates']) > 0:
        cert_list = [cert for cert in profile_data['certificates'] if cert.get('name')]
        if cert_list:
            story.append(Paragraph('CERTIFICATIONS', header_style))
            for cert in cert_list:
                cert_name = f"<b>{cert.get('name', '')}</b>"
                story.append(Paragraph(cert_name, styles['Normal']))
                
                cert_info = cert.get('issuer', '')
                if cert.get('issueDate'):
                    try:
                        issue_date = datetime.fromisoformat(cert['issueDate'].replace('Z', '+00:00'))
                        cert_info += f" ({issue_date.strftime('%B %Y')})"
                    except:
                        pass
                
                if cert_info:
                    story.append(Paragraph(cert_info, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    return buffer

def create_creative_template(profile_data, buffer):
    """Creative Bold template with vibrant purple/pink design"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.75*inch, rightMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles with purple theme
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=26,
        textColor=colors.HexColor('#9333ea'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#9333ea'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    # Name
    story.append(Paragraph(profile_data['name'], title_style))
    
    # Contact info
    contact_parts = []
    if profile_data.get('email'):
        contact_parts.append(profile_data['email'])
    if profile_data.get('phone'):
        contact_parts.append(profile_data['phone'])
    if profile_data.get('location'):
        contact_parts.append(profile_data['location'])
    
    if contact_parts:
        contact_text = ' ◆ '.join(contact_parts)
        story.append(Paragraph(contact_text, ParagraphStyle('Contact', parent=styles['Normal'], 
                                                            alignment=TA_CENTER, fontSize=10,
                                                            textColor=colors.HexColor('#c026d3'))))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Summary
    if profile_data.get('summary'):
        story.append(Paragraph('ABOUT ME', header_style))
        story.append(Paragraph(profile_data['summary'], styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Skills with visual formatting
    if profile_data.get('skills') and len(profile_data['skills']) > 0:
        story.append(Paragraph('SKILLS & EXPERTISE', header_style))
        skills_text = ' ◆ '.join(profile_data['skills'])
        story.append(Paragraph(skills_text, ParagraphStyle('Skills', parent=styles['Normal'],
                                                          textColor=colors.HexColor('#7c3aed'))))
        story.append(Spacer(1, 0.15*inch))
    
    # Experience
    if profile_data.get('experience') and len(profile_data['experience']) > 0:
        exp_list = [exp for exp in profile_data['experience'] if exp.get('company')]
        if exp_list:
            story.append(Paragraph('EXPERIENCE', header_style))
            for exp in exp_list:
                job_title = f"<b>{exp.get('role', '')}</b>"
                story.append(Paragraph(job_title, ParagraphStyle('JobTitle', parent=styles['Normal'],
                                                                textColor=colors.HexColor('#9333ea'))))
                
                company_duration = exp.get('company', '')
                if exp.get('duration'):
                    company_duration += f" • {exp['duration']}"
                story.append(Paragraph(company_duration, styles['Normal']))
                
                if exp.get('description'):
                    story.append(Paragraph(exp['description'], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Education
    if profile_data.get('education') and len(profile_data['education']) > 0:
        edu_list = [edu for edu in profile_data['education'] if edu.get('degree')]
        if edu_list:
            story.append(Paragraph('EDUCATION', header_style))
            for edu in edu_list:
                degree = f"<b>{edu.get('degree', '')}</b>"
                story.append(Paragraph(degree, ParagraphStyle('Degree', parent=styles['Normal'],
                                                             textColor=colors.HexColor('#9333ea'))))
                
                institution_text = edu.get('institution', '')
                if edu.get('startYear') or edu.get('endYear'):
                    institution_text += f" • {edu.get('startYear', '')} - {edu.get('endYear', '')}"
                if edu.get('gpa'):
                    institution_text += f" • GPA: {edu['gpa']}"
                
                story.append(Paragraph(institution_text, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Projects
    if profile_data.get('projects') and len(profile_data['projects']) > 0:
        proj_list = [proj for proj in profile_data['projects'] if proj.get('name')]
        if proj_list:
            story.append(Paragraph('PROJECTS', header_style))
            for proj in proj_list:
                project_name = f"<b>{proj.get('name', '')}</b>"
                story.append(Paragraph(project_name, ParagraphStyle('ProjectName', parent=styles['Normal'],
                                                                   textColor=colors.HexColor('#9333ea'))))
                if proj.get('description'):
                    story.append(Paragraph(proj['description'], styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    # Certifications
    if profile_data.get('certificates') and len(profile_data['certificates']) > 0:
        cert_list = [cert for cert in profile_data['certificates'] if cert.get('name')]
        if cert_list:
            story.append(Paragraph('CERTIFICATIONS', header_style))
            for cert in cert_list:
                cert_name = f"<b>{cert.get('name', '')}</b>"
                story.append(Paragraph(cert_name, styles['Normal']))
                
                cert_info = cert.get('issuer', '')
                if cert.get('issueDate'):
                    try:
                        issue_date = datetime.fromisoformat(cert['issueDate'].replace('Z', '+00:00'))
                        cert_info += f" • {issue_date.strftime('%B %Y')}"
                    except:
                        pass
                
                if cert_info:
                    story.append(Paragraph(cert_info, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    return buffer

def create_minimal_template(profile_data, buffer):
    """Minimal Clean template with green accents"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          topMargin=0.75*inch, bottomMargin=0.75*inch,
                          leftMargin=1*inch, rightMargin=1*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom minimal styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#059669'),
        spaceAfter=8,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#059669'),
        spaceAfter=8,
        spaceBefore=16,
        fontName='Helvetica-Bold'
    )
    
    # Name
    story.append(Paragraph(profile_data['name'], title_style))
    
    # Contact info - simple and clean
    contact_parts = []
    if profile_data.get('email'):
        contact_parts.append(profile_data['email'])
    if profile_data.get('phone'):
        contact_parts.append(profile_data['phone'])
    if profile_data.get('location'):
        contact_parts.append(profile_data['location'])
    
    if contact_parts:
        contact_text = ' • '.join(contact_parts)
        story.append(Paragraph(contact_text, ParagraphStyle('Contact', parent=styles['Normal'], 
                                                            fontSize=9)))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Summary
    if profile_data.get('summary'):
        story.append(Paragraph('Summary', header_style))
        story.append(Paragraph(profile_data['summary'], styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    # Experience
    if profile_data.get('experience') and len(profile_data['experience']) > 0:
        exp_list = [exp for exp in profile_data['experience'] if exp.get('company')]
        if exp_list:
            story.append(Paragraph('Experience', header_style))
            for exp in exp_list:
                job_title = f"<b>{exp.get('role', '')}</b> — {exp.get('company', '')}"
                story.append(Paragraph(job_title, styles['Normal']))
                
                if exp.get('duration'):
                    story.append(Paragraph(exp['duration'], ParagraphStyle('Duration', parent=styles['Normal'],
                                                                          fontSize=9, textColor=colors.grey)))
                
                if exp.get('description'):
                    story.append(Paragraph(exp['description'], styles['Normal']))
                story.append(Spacer(1, 0.12*inch))
    
    # Education
    if profile_data.get('education') and len(profile_data['education']) > 0:
        edu_list = [edu for edu in profile_data['education'] if edu.get('degree')]
        if edu_list:
            story.append(Paragraph('Education', header_style))
            for edu in edu_list:
                degree = f"<b>{edu.get('degree', '')}</b> — {edu.get('institution', '')}"
                story.append(Paragraph(degree, styles['Normal']))
                
                edu_details = []
                if edu.get('startYear') or edu.get('endYear'):
                    edu_details.append(f"{edu.get('startYear', '')} - {edu.get('endYear', '')}")
                if edu.get('gpa'):
                    edu_details.append(f"GPA: {edu['gpa']}")
                
                if edu_details:
                    story.append(Paragraph(' • '.join(edu_details), ParagraphStyle('EduDetails', 
                                                                                   parent=styles['Normal'],
                                                                                   fontSize=9, textColor=colors.grey)))
                story.append(Spacer(1, 0.12*inch))
    
    # Skills
    if profile_data.get('skills') and len(profile_data['skills']) > 0:
        story.append(Paragraph('Skills', header_style))
        skills_text = ', '.join(profile_data['skills'])
        story.append(Paragraph(skills_text, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    # Projects
    if profile_data.get('projects') and len(profile_data['projects']) > 0:
        proj_list = [proj for proj in profile_data['projects'] if proj.get('name')]
        if proj_list:
            story.append(Paragraph('Projects', header_style))
            for proj in proj_list:
                project_name = f"<b>{proj.get('name', '')}</b>"
                story.append(Paragraph(project_name, styles['Normal']))
                if proj.get('description'):
                    story.append(Paragraph(proj['description'], styles['Normal']))
                story.append(Spacer(1, 0.12*inch))
    
    # Certifications
    if profile_data.get('certificates') and len(profile_data['certificates']) > 0:
        cert_list = [cert for cert in profile_data['certificates'] if cert.get('name')]
        if cert_list:
            story.append(Paragraph('Certifications', header_style))
            for cert in cert_list:
                cert_name = cert.get('name', '')
                cert_issuer = cert.get('issuer', '')
                
                cert_text = f"<b>{cert_name}</b>"
                if cert_issuer:
                    cert_text += f" — {cert_issuer}"
                
                story.append(Paragraph(cert_text, styles['Normal']))
                
                if cert.get('issueDate'):
                    try:
                        issue_date = datetime.fromisoformat(cert['issueDate'].replace('Z', '+00:00'))
                        story.append(Paragraph(issue_date.strftime('%B %Y'), 
                                             ParagraphStyle('CertDate', parent=styles['Normal'],
                                                          fontSize=9, textColor=colors.grey)))
                    except:
                        pass
                
                story.append(Spacer(1, 0.12*inch))
    
    doc.build(story)
    return buffer

@resume_bp.route('/generate-resume', methods=['POST'])
def generate_resume():
    """Generate a PDF resume based on template and profile data"""
    try:
        data = request.json
        template = data.get('template', 'modern')
        profile = data.get('profile', {})
        
        if not profile:
            return jsonify({'error': 'Profile data is required'}), 400
        
        # Create PDF in memory
        buffer = BytesIO()
        
        # Select template
        if template == 'modern':
            create_modern_template(profile, buffer)
        elif template == 'classic':
            create_classic_template(profile, buffer)
        elif template == 'creative':
            create_creative_template(profile, buffer)
        elif template == 'minimal':
            create_minimal_template(profile, buffer)
        else:
            create_modern_template(profile, buffer)  # Default to modern
        
        buffer.seek(0)
        
        # Send the PDF file
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{profile.get('name', 'Resume').replace(' ', '_')}_Resume.pdf"
        )
        
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return jsonify({'error': 'Failed to generate resume', 'details': str(e)}), 500
