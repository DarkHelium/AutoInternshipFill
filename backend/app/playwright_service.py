"""
Playwright Service for Enhanced Form Filling
Provides better job scraping and form automation
"""
import asyncio
import json
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Browser, Page
import logging

logger = logging.getLogger(__name__)

class PlaywrightService:
    """Enhanced web automation service using Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def handle_intermediate_apply_page(self, page: Page) -> None:
        """Handle intermediate pages that require clicking Apply button to get to job description"""
        try:
            # Look for Apply buttons or similar navigation elements
            apply_selectors = [
                # Common Apply button selectors
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                '[role="button"]:has-text("Apply")',
                
                # View Job selectors
                'button:has-text("View Job")',
                'a:has-text("View Job")',
                'button:has-text("View Details")',
                'a:has-text("View Details")',
                
                # Continue/Proceed selectors
                'button:has-text("Continue")',
                'a:has-text("Continue")',
                'button:has-text("Proceed")',
                'a:has-text("Proceed")',
                
                # Generic class/id based selectors
                '.apply-button', '.apply-btn', '#apply-button',
                '.view-job', '.job-details-btn',
                '[data-automation-id="apply"]',
                '[data-testid="apply"]',
                '[data-qa="apply"]'
            ]
            
            # Try each selector to find and click Apply button
            for selector in apply_selectors:
                try:
                    apply_element = await page.wait_for_selector(selector, timeout=3000)
                    if apply_element:
                        logger.info(f"Found Apply button with selector: {selector}")
                        
                        # Check if it's a link that opens in new tab/window
                        href = await apply_element.get_attribute('href')
                        if href and href.startswith('http'):
                            # Navigate directly to the job posting URL
                            await page.goto(href, wait_until='networkidle')
                            await page.wait_for_timeout(2000)
                            logger.info(f"Navigated to job posting: {href}")
                            return
                        else:
                            # Click the button/element
                            await apply_element.click()
                            await page.wait_for_timeout(3000)  # Wait for navigation
                            logger.info(f"Clicked Apply button, waiting for page load")
                            return
                            
                except Exception as e:
                    logger.debug(f"Apply selector {selector} failed: {e}")
                    continue
            
            # If no Apply button found, check if we're already on a job description page
            job_indicators = [
                '[data-automation-id="jobPostingDescription"]',  # Workday
                '.job-description', '.job-details',
                '.job-post-content', '.job-content',
                'h1[data-automation-id="jobPostingHeader"]'  # Workday job title
            ]
            
            for indicator in job_indicators:
                try:
                    element = await page.wait_for_selector(indicator, timeout=2000)
                    if element:
                        logger.info("Already on job description page")
                        return
                except:
                    continue
            
            logger.info("No Apply button found, proceeding with current page")
            
        except Exception as e:
            logger.error(f"Error handling intermediate page: {e}")
            # Continue with current page if Apply button handling fails
    
    async def scrape_job_details(self, job_url: str) -> Dict[str, Any]:
        """Enhanced job scraping with Playwright, handles intermediate pages with Apply buttons"""
        try:
            page = await self.browser.new_page()
            await page.goto(job_url, wait_until='networkidle')
            
            # Wait for initial page to load
            await page.wait_for_timeout(2000)
            
            # Check if this is an intermediate page with an Apply button
            await self.handle_intermediate_apply_page(page)
            
            # Extract job information with better selectors
            job_data = await page.evaluate("""
                () => {
                    // Extract company name with multiple strategies
                    function extractCompany() {
                        const selectors = [
                            // Greenhouse specific
                            '.company-name', '.app-title', '[data-qa="company-name"]',
                            '.header .company', 'h1 + div', '.job-header .company',
                            
                            // LinkedIn specific  
                            '.job-details-jobs-unified-top-card__primary-description',
                            '.job-details-jobs-unified-top-card__company-name',
                            
                            // Workday specific
                            '[data-automation-id="jobPostingCompanyName"]',
                            
                            // General selectors
                            '.company-name', '.job-company', '.company', '.organization-name',
                            '[class*="company"]', '[id*="company"]'
                        ];
                        
                        for (const selector of selectors) {
                            const element = document.querySelector(selector);
                            if (element && element.textContent.trim()) {
                                let company = element.textContent.trim();
                                // Clean up common prefixes/suffixes
                                company = company.replace(/^(at\\s+|@\\s+)/i, '');
                                company = company.replace(/(\\s+careers?|\\s+jobs?)$/i, '');
                                return company;
                            }
                        }
                        
                        // Try to extract from page title
                        const title = document.title;
                        const titleMatch = title.match(/(.+?)\\s+[-|–]\\s+(careers?|jobs?)/i);
                        if (titleMatch) {
                            return titleMatch[1].trim();
                        }
                        
                        // Try to extract from URL
                        const hostname = window.location.hostname;
                        if (hostname.includes('greenhouse.io')) {
                            const pathMatch = window.location.pathname.match(/\\/([^\\/]+)\\/jobs/);
                            if (pathMatch) return pathMatch[1];
                        }
                        
                        // Fallback to cleaned domain
                        return hostname.replace(/^(www\\.|jobs\\.|careers\\.)/, '').split('.')[0];
                    }
                    
                    // Extract job title - look for content that looks like a job title
                    function extractTitle() {
                        const selectors = [
                            // Specific ATS selectors
                            'h1[data-automation-id="jobPostingHeader"]', // Workday
                            '.job-title', '.job-details-jobs-unified-top-card__job-title',
                            'h1.job-post-header__title', // Greenhouse
                            '[data-testid="job-title"]', // Ashby
                            
                            // Generic job title selectors
                            '[class*="job-title"]', '[id*="job-title"]',
                            '[class*="position-title"]', '[id*="position-title"]',
                            '[class*="role-title"]', '[id*="role-title"]',
                            
                            // Header elements that might contain job titles
                            'h1', 'h2', 'h3'
                        ];
                        
                        // Job title keywords to validate if text looks like a job title
                        const jobTitleKeywords = [
                            'engineer', 'developer', 'analyst', 'manager', 'director', 'lead',
                            'senior', 'junior', 'associate', 'specialist', 'coordinator',
                            'architect', 'consultant', 'designer', 'scientist', 'researcher',
                            'intern', 'trainee', 'officer', 'executive', 'supervisor'
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            for (const element of elements) {
                                const text = element.textContent.trim();
                                if (text && text.length > 5 && text.length < 100) {
                                    // Check if it looks like a job title
                                    const lowerText = text.toLowerCase();
                                    const hasJobKeyword = jobTitleKeywords.some(keyword => 
                                        lowerText.includes(keyword)
                                    );
                                    
                                    // Additional checks for job title patterns
                                    const hasJobPattern = /\\b(software|data|product|marketing|sales|operations|finance|hr|human resources)\\b/i.test(text);
                                    
                                    if (hasJobKeyword || hasJobPattern) {
                                        return text;
                                    }
                                }
                            }
                        }
                        
                        // Fallback to page title
                        const pageTitle = document.title;
                        const titleParts = pageTitle.split(' - ');
                        if (titleParts.length > 0) {
                            const firstPart = titleParts[0].trim();
                            const lowerFirst = firstPart.toLowerCase();
                            const hasJobKeyword = jobTitleKeywords.some(keyword => 
                                lowerFirst.includes(keyword)
                            );
                            if (hasJobKeyword) {
                                return firstPart;
                            }
                        }
                        
                        return pageTitle.split(' - ')[0];
                    }
                    
                    // Extract location
                    function extractLocation() {
                        const selectors = [
                            '.job-details-jobs-unified-top-card__bullet',
                            '.location', '.job-location',
                            '[data-automation-id="jobPostingLocation"]',
                            '[class*="location"]', '[id*="location"]'
                        ];
                        
                        for (const selector of selectors) {
                            const element = document.querySelector(selector);
                            if (element && element.textContent.trim()) {
                                return element.textContent.trim();
                            }
                        }
                        return null;
                    }
                    
                    // Extract job description - smart detection of job-related content
                    function extractDescription() {
                        const selectors = [
                            // Workday specific selectors
                            '[data-automation-id="jobPostingDescription"]',
                            '[data-automation-id="job-details"]',
                            
                            // LinkedIn specific
                            '.job-details-jobs-unified-top-card__job-description',
                            '.job-description-content',
                            
                            // Greenhouse specific
                            '.job-post-content',
                            '.content',
                            
                            // Generic selectors
                            '.job-description', '.job-details',
                            '.job-content', '.posting-content',
                            '.description', '.details',
                            
                            // Fallback selectors
                            '[class*="description"]',
                            '[class*="content"]',
                            '[id*="description"]',
                            'main', '.main-content'
                        ];
                        
                        // Job description keywords to validate content
                        const jobDescKeywords = [
                            'responsibilities', 'requirements', 'qualifications', 'skills',
                            'experience', 'education', 'bachelor', 'master', 'degree',
                            'years of experience', 'preferred', 'required', 'must have',
                            'nice to have', 'benefits', 'salary', 'compensation',
                            'role', 'position', 'candidate', 'team', 'company', 'we are looking'
                        ];
                        
                        function scoreJobContent(text) {
                            const lowerText = text.toLowerCase();
                            let score = 0;
                            
                            // Count job-related keywords
                            jobDescKeywords.forEach(keyword => {
                                if (lowerText.includes(keyword)) {
                                    score += keyword.length; // Longer keywords get more weight
                                }
                            });
                            
                            // Bonus for common job description sections
                            if (lowerText.includes('about this role') || lowerText.includes('job summary')) score += 20;
                            if (lowerText.includes('what you\\'ll do') || lowerText.includes('responsibilities')) score += 15;
                            if (lowerText.includes('what we\\'re looking for') || lowerText.includes('requirements')) score += 15;
                            if (lowerText.includes('qualifications') || lowerText.includes('skills')) score += 10;
                            
                            return score;
                        }
                        
                        let bestContent = '';
                        let bestScore = 0;
                        
                        // Try specific selectors first
                        for (const selector of selectors) {
                            const element = document.querySelector(selector);
                            if (element) {
                                let text = element.innerText || element.textContent;
                                if (text && text.trim().length > 100) {
                                    const score = scoreJobContent(text);
                                    if (score > bestScore) {
                                        bestScore = score;
                                        bestContent = text.replace(/\\s+/g, ' ').trim();
                                    }
                                }
                            }
                        }
                        
                        if (bestContent && bestScore > 10) {
                            return bestContent;
                        }
                        
                        // Try to find content by analyzing all text sections
                        const allElements = document.querySelectorAll('div, section, article, p');
                        for (const element of allElements) {
                            const text = element.innerText || element.textContent;
                            if (text && text.trim().length > 200 && text.trim().length < 10000) {
                                const score = scoreJobContent(text);
                                if (score > bestScore && score > 20) {
                                    bestScore = score;
                                    bestContent = text.replace(/\\s+/g, ' ').trim();
                                }
                            }
                        }
                        
                        if (bestContent) {
                            return bestContent.substring(0, 8000);
                        }
                        
                        // Last resort: main content areas
                        const mainElements = document.querySelectorAll('main, .main, #main, [role="main"]');
                        for (const main of mainElements) {
                            const text = main.innerText || main.textContent;
                            if (text && text.trim().length > 200) {
                                return text.replace(/\\s+/g, ' ').trim().substring(0, 8000);
                            }
                        }
                        
                        return 'No job description found';
                    }
                    
                    // Detect ATS platform
                    function detectATS() {
                        const url = window.location.href;
                        const hostname = window.location.hostname;
                        
                        if (hostname.includes('greenhouse.io')) return 'greenhouse';
                        if (hostname.includes('lever.co')) return 'lever';
                        if (hostname.includes('ashbyhq.com')) return 'ashby';
                        if (hostname.includes('icims.com')) return 'icims';
                        if (hostname.includes('workday.com') || hostname.includes('myworkdayjobs.com')) return 'workday';
                        if (hostname.includes('linkedin.com')) return 'linkedin';
                        if (url.includes('bamboohr.com')) return 'bamboo';
                        
                        return 'unknown';
                    }
                    
                    return {
                        company: extractCompany(),
                        title: extractTitle(),
                        location: extractLocation(),
                        description: extractDescription(),
                        ats: detectATS(),
                        url: window.location.href
                    };
                }
            """)
            
            # Log the extracted data for debugging
            logger.info(f"Extracted job data from {page.url}: company='{job_data.get('company')}', title='{job_data.get('title')}', description_length={len(job_data.get('description', ''))}")
            
            await page.close()
            return job_data
            
        except Exception as e:
            logger.error(f"Enhanced job scraping failed: {e}")
            return {
                'company': 'Unknown',
                'title': 'Unknown',
                'location': None,
                'description': '',
                'ats': 'unknown',
                'url': job_url
            }
    
    async def analyze_form_fields(self, job_url: str) -> Dict[str, Any]:
        """Analyze available form fields on the job application page"""
        try:
            page = await self.browser.new_page()
            await page.goto(job_url, wait_until='networkidle')
            
            # Look for application forms
            form_info = await page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    const fields = [];
                    
                    forms.forEach(form => {
                        const inputs = form.querySelectorAll('input, textarea, select');
                        inputs.forEach(input => {
                            if (input.type !== 'hidden' && input.type !== 'submit') {
                                fields.push({
                                    type: input.type || input.tagName.toLowerCase(),
                                    name: input.name || '',
                                    id: input.id || '',
                                    placeholder: input.placeholder || '',
                                    className: input.className || '',
                                    required: input.required || false
                                });
                            }
                        });
                    });
                    
                    return {
                        fieldsFound: fields.length,
                        fields: fields,
                        hasApplicationForm: fields.length > 3
                    };
                }
            """)
            
            await page.close()
            return form_info
            
        except Exception as e:
            logger.error(f"Form analysis failed: {e}")
            return {'fieldsFound': 0, 'fields': [], 'hasApplicationForm': False}
    
    async def fill_application_form(self, job_url: str, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fill application form with resume data using Playwright"""
        try:
            page = await self.browser.new_page()
            await page.goto(job_url, wait_until='networkidle')
            
            # Extract contact info from resume
            contact = resume_data.get('contact', {})
            name_parts = resume_data.get('name', '').split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            filled_fields = []
            
            # Fill name fields
            if first_name:
                selectors = [
                    'input[name*="first"], input[name*="fname"], input[placeholder*="First" i]',
                    'input[id*="first"], input[class*="first"]'
                ]
                for selector in selectors:
                    try:
                        await page.fill(selector, first_name, timeout=1000)
                        filled_fields.append('first_name')
                        break
                    except:
                        continue
            
            if last_name:
                selectors = [
                    'input[name*="last"], input[name*="lname"], input[placeholder*="Last" i]',
                    'input[id*="last"], input[class*="last"]'
                ]
                for selector in selectors:
                    try:
                        await page.fill(selector, last_name, timeout=1000)
                        filled_fields.append('last_name')
                        break
                    except:
                        continue
            
            # Fill email
            if contact.get('email'):
                selectors = [
                    'input[type="email"]',
                    'input[name*="email"], input[placeholder*="email" i]'
                ]
                for selector in selectors:
                    try:
                        await page.fill(selector, contact['email'], timeout=1000)
                        filled_fields.append('email')
                        break
                    except:
                        continue
            
            # Fill phone
            if contact.get('phone'):
                selectors = [
                    'input[type="tel"]',
                    'input[name*="phone"], input[placeholder*="phone" i]'
                ]
                for selector in selectors:
                    try:
                        await page.fill(selector, contact['phone'], timeout=1000)
                        filled_fields.append('phone')
                        break
                    except:
                        continue
            
            # Fill cover letter/summary
            if resume_data.get('summary'):
                selectors = [
                    'textarea[name*="cover"], textarea[placeholder*="cover" i]',
                    'textarea[name*="summary"], textarea[placeholder*="summary" i]'
                ]
                for selector in selectors:
                    try:
                        await page.fill(selector, resume_data['summary'], timeout=1000)
                        filled_fields.append('cover_letter')
                        break
                    except:
                        continue
            
            await page.close()
            
            return {
                'success': True,
                'fields_filled': len(filled_fields),
                'filled_fields': filled_fields
            }
            
        except Exception as e:
            logger.error(f"Playwright form filling failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'fields_filled': 0,
                'filled_fields': []
            }

# Utility function
async def enhanced_job_scraping(job_url: str) -> Dict[str, Any]:
    """Standalone function for enhanced job scraping"""
    async with PlaywrightService() as playwright_service:
        return await playwright_service.scrape_job_details(job_url)
