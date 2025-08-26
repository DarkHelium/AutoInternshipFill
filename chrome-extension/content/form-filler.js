// Form Filler Content Script
// This script handles intelligent form filling for job applications

class FormFiller {
  constructor() {
    this.init();
  }

  init() {
    console.log('AI Career Co-pilot: Form filler initialized');
    
    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'fillForm') {
        this.fillForm(request.data)
          .then(sendResponse)
          .catch(error => sendResponse({ error: error.message }));
        return true; // Keep message channel open
      }
    });
  }

  async fillForm(resumeData) {
    try {
      console.log('Starting intelligent form fill...', resumeData);
      
      if (!resumeData || !resumeData.tailored_resume) {
        throw new Error('No resume data provided');
      }

      const resume = resumeData.tailored_resume;
      let filledCount = 0;

      // Basic contact information
      filledCount += this.fillContactInfo(resume);
      
      // Experience and skills
      filledCount += this.fillExperienceInfo(resume);
      
      // Education
      filledCount += this.fillEducationInfo(resume);
      
      // Show success notification
      this.showNotification(`Successfully filled ${filledCount} fields!`, 'success');
      
      return { success: true, fieldsCount: filledCount };
      
    } catch (error) {
      console.error('Form filling failed:', error);
      this.showNotification('Form filling failed: ' + error.message, 'error');
      throw error;
    }
  }

  fillContactInfo(resume) {
    let count = 0;
    const contact = resume.contact || {};
    
    // Name fields
    if (resume.name) {
      const nameParts = resume.name.split(' ');
      const firstName = nameParts[0];
      const lastName = nameParts.slice(1).join(' ');
      
      count += this.fillFieldsBySelectors([
        'input[name*="first"], input[name*="fname"], input[placeholder*="First" i]',
        'input[id*="first"], input[class*="first"]'
      ], firstName);
      
      count += this.fillFieldsBySelectors([
        'input[name*="last"], input[name*="lname"], input[placeholder*="Last" i]',
        'input[id*="last"], input[class*="last"]'
      ], lastName);
      
      // Full name fields
      count += this.fillFieldsBySelectors([
        'input[name*="name"], input[placeholder*="Name" i]',
        'input[id*="name"], input[class*="name"]'
      ], resume.name);
    }
    
    // Email
    if (contact.email) {
      count += this.fillFieldsBySelectors([
        'input[type="email"]',
        'input[name*="email"], input[placeholder*="email" i]',
        'input[id*="email"], input[class*="email"]'
      ], contact.email);
    }
    
    // Phone
    if (contact.phone) {
      count += this.fillFieldsBySelectors([
        'input[type="tel"]',
        'input[name*="phone"], input[placeholder*="phone" i]',
        'input[id*="phone"], input[class*="phone"]'
      ], contact.phone);
    }
    
    // Location
    if (contact.location) {
      count += this.fillFieldsBySelectors([
        'input[name*="location"], input[placeholder*="location" i]',
        'input[name*="city"], input[placeholder*="city" i]',
        'input[id*="location"], input[class*="location"]'
      ], contact.location);
    }
    
    // LinkedIn
    if (contact.linkedin) {
      count += this.fillFieldsBySelectors([
        'input[name*="linkedin"], input[placeholder*="linkedin" i]',
        'input[id*="linkedin"], input[class*="linkedin"]'
      ], contact.linkedin);
    }
    
    // GitHub
    if (contact.github) {
      count += this.fillFieldsBySelectors([
        'input[name*="github"], input[placeholder*="github" i]',
        'input[id*="github"], input[class*="github"]'
      ], contact.github);
    }
    
    return count;
  }

  fillExperienceInfo(resume) {
    let count = 0;
    
    // Summary/Cover letter
    if (resume.summary) {
      count += this.fillFieldsBySelectors([
        'textarea[name*="summary"], textarea[placeholder*="summary" i]',
        'textarea[name*="cover"], textarea[placeholder*="cover" i]',
        'textarea[id*="summary"], textarea[class*="summary"]'
      ], resume.summary);
    }
    
    // Skills
    if (resume.skills && Array.isArray(resume.skills)) {
      const skillsText = resume.skills.join(', ');
      count += this.fillFieldsBySelectors([
        'textarea[name*="skill"], textarea[placeholder*="skill" i]',
        'input[name*="skill"], input[placeholder*="skill" i]',
        'textarea[id*="skill"], textarea[class*="skill"]'
      ], skillsText);
    }
    
    return count;
  }

  fillEducationInfo(resume) {
    let count = 0;
    
    if (resume.education && resume.education.length > 0) {
      const edu = resume.education[0]; // Use first education entry
      
      // University/School
      if (edu.school) {
        count += this.fillFieldsBySelectors([
          'input[name*="school"], input[placeholder*="school" i]',
          'input[name*="university"], input[placeholder*="university" i]',
          'input[id*="school"], input[class*="school"]'
        ], edu.school);
      }
      
      // Degree
      if (edu.degree) {
        count += this.fillFieldsBySelectors([
          'input[name*="degree"], input[placeholder*="degree" i]',
          'select[name*="degree"]',
          'input[id*="degree"], input[class*="degree"]'
        ], edu.degree);
      }
      
      // Graduation date
      if (edu.graduation) {
        count += this.fillFieldsBySelectors([
          'input[name*="graduation"], input[placeholder*="graduation" i]',
          'input[name*="grad"], input[placeholder*="grad" i]',
          'input[id*="graduation"], input[class*="graduation"]'
        ], edu.graduation);
      }
    }
    
    return count;
  }

  fillFieldsBySelectors(selectors, value) {
    if (!value) return 0;
    
    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);
      for (const element of elements) {
        if (element && !element.value && !element.disabled && element.offsetParent !== null) {
          this.fillField(element, value);
          return 1; // Only fill the first empty, visible field
        }
      }
    }
    return 0;
  }

  fillField(element, value) {
    // Set the value
    element.value = value;
    
    // Trigger events to notify the page
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new Event('blur', { bubbles: true }));
    
    // Add visual feedback
    element.classList.add('ai-copilot-filled');
    setTimeout(() => {
      element.classList.remove('ai-copilot-filled');
    }, 2000);
  }

  showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `ai-copilot-notification ai-copilot-notification-${type}`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 10000;
      padding: 12px 20px;
      border-radius: 8px;
      color: white;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      animation: slideInRight 0.3s ease;
      background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 5000);
  }
}

// Initialize form filler
new FormFiller();
