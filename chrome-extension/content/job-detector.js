// Job Detection and Analysis Content Script
class JobDetector {
  constructor() {
    this.currentJob = null;
    this.init();
  }

  init() {
    console.log('AI Career Co-pilot: Job detector initialized on', window.location.href);
    
    // Detect job page and extract information
    this.detectJobPage();
    
    // Add floating action button
    this.addFloatingButton();
    
    // Listen for page changes (SPA navigation)
    this.observePageChanges();
    
    // Debug: Show current job data in console
    if (this.currentJob) {
      console.log('AI Career Co-pilot: Job detected:', this.currentJob);
    } else {
      console.log('AI Career Co-pilot: No job detected on this page');
    }
  }

  detectJobPage() {
    const url = window.location.href;
    const title = document.title;
    
    // Skip common non-job sites to avoid unnecessary processing
    const skipDomains = ['google.com', 'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com', 'github.com'];
    const hostname = window.location.hostname.toLowerCase();
    if (skipDomains.some(domain => hostname.includes(domain))) {
      return;
    }
    
    // Check if this looks like a job posting
    const jobIndicators = [
      'job', 'career', 'position', 'role', 'opening', 'opportunity',
      'software engineer', 'developer', 'analyst', 'manager', 'engineer',
      'specialist', 'coordinator', 'associate', 'intern', 'trainee',
      'director', 'lead', 'senior', 'junior', 'architect', 'consultant'
    ];
    
    const jobUrlPatterns = [
      '/jobs/', '/careers/', '/job/', '/career/', '/positions/', '/openings/',
      'greenhouse.io', 'lever.co', 'workday.com', 'myworkdayjobs.com',
      'ashbyhq.com', 'icims.com', 'bamboohr.com', 'careers.jnj.com',
      'internship', 'intern', 'summer', 'technology', 'program'
    ];
    
    // Require either strong URL indicators OR title + URL combination
    const hasStrongUrlIndicator = jobUrlPatterns.some(pattern => 
      url.toLowerCase().includes(pattern)
    );
    
    const hasTitleIndicator = jobIndicators.some(indicator => 
      title.toLowerCase().includes(indicator)
    );
    
    const hasUrlIndicator = jobIndicators.some(indicator => 
      url.toLowerCase().includes(indicator)
    );
    
    const isJobPage = hasStrongUrlIndicator || (hasTitleIndicator && hasUrlIndicator);
    
    console.log('AI Career Co-pilot: Job page check:', { 
      isJobPage, 
      hasStrongUrlIndicator,
      hasTitleIndicator,
      hasUrlIndicator,
      url, 
      title 
    });
    
    if (isJobPage) {
      this.extractJobInfo();
    }
  }

  extractJobInfo() {
    const jobData = {
      url: window.location.href,
      title: this.extractJobTitle(),
      company: this.extractCompany(),
      location: this.extractLocation(),
      description: this.extractJobDescription(),
      requirements: this.extractRequirements(),
      ats: this.detectATS()
    };
    
    this.currentJob = jobData;
    console.log('Job detected:', jobData);
    
    // Auto-analyze if enabled
    this.checkAutoAnalyze();
  }

  extractJobTitle() {
    const selectors = [
      'h1[data-automation-id="jobPostingHeader"]', // Workday
      '.job-title', '.job-details-jobs-unified-top-card__job-title',
      'h1.job-post-header__title', // Greenhouse
      '[data-testid="job-title"]', // Ashby
      'h1', 'h2', '.title'
    ];
    
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) {
        return element.textContent.trim();
      }
    }
    
    // Fallback to page title
    return document.title.split(' - ')[0];
  }

  extractCompany() {
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
        company = company.replace(/^(at\s+|@\s+)/i, '');
        company = company.replace(/(\s+careers?|\s+jobs?)$/i, '');
        return company;
      }
    }
    
    // Try to extract from page title
    const title = document.title;
    const titleMatch = title.match(/(.+?)\s+[-|–]\s+(careers?|jobs?)/i);
    if (titleMatch) {
      return titleMatch[1].trim();
    }
    
    // Try to extract from URL
    const hostname = window.location.hostname;
    if (hostname.includes('greenhouse.io')) {
      const pathMatch = window.location.pathname.match(/\/([^\/]+)\/jobs/);
      if (pathMatch) return pathMatch[1];
    }
    
    // Fallback to cleaned domain
    return hostname.replace(/^(www\.|jobs\.|careers\.)/, '').split('.')[0];
  }

  extractLocation() {
    const selectors = [
      '.job-details-jobs-unified-top-card__bullet',
      '.location', '.job-location',
      '[data-automation-id="jobPostingLocation"]'
    ];
    
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) {
        return element.textContent.trim();
      }
    }
    
    return null;
  }

  extractJobDescription() {
    const selectors = [
      '.job-details-jobs-unified-top-card__job-description',
      '.job-description', '.job-details',
      '[data-automation-id="jobPostingDescription"]',
      '.job-post-content', '.content',
      'main', '.main-content'
    ];
    
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) {
        // Clean up the text
        const text = element.innerText || element.textContent;
        return text.replace(/\s+/g, ' ').trim();
      }
    }
    
    // Fallback to body text
    return document.body.innerText.substring(0, 5000);
  }

  extractRequirements() {
    const description = this.extractJobDescription().toLowerCase();
    const requirements = [];
    
    // Look for common requirement patterns
    const patterns = [
      /(\d+)\s*\+?\s*years?\s+(?:of\s+)?experience/g,
      /bachelor'?s?\s+degree/g,
      /master'?s?\s+degree/g,
      /phd/g,
      /javascript|python|java|react|node|sql/g
    ];
    
    patterns.forEach(pattern => {
      const matches = description.match(pattern);
      if (matches) {
        requirements.push(...matches);
      }
    });
    
    return requirements;
  }

  detectATS() {
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

  async checkAutoAnalyze() {
    const settings = await chrome.storage.sync.get(['autoAnalyze']);
    if (settings.autoAnalyze && this.currentJob) {
      this.analyzeCurrentJob();
    }
  }

  async analyzeCurrentJob() {
    if (!this.currentJob) return;
    
    try {
      // Check if user has uploaded a resume first
      const hasResume = await this.checkResumeUploaded();
      if (!hasResume) {
        this.showNotification('Please upload your resume first in the extension settings', 'warning');
        this.showResumeUploadPrompt();
        return;
      }
      
      this.showNotification('Analyzing job with AI...', 'info');
      
      const response = await chrome.runtime.sendMessage({
        action: 'analyzeJob',
        data: {
          jobUrl: this.currentJob.url,
          jobDescription: this.currentJob.description
        }
      });
      
      if (response.error) {
        throw new Error(response.error);
      }
      
      this.showNotification(`Job analyzed! Match score: ${Math.round(response.match_score * 100)}%`, 'success');
      this.updateFloatingButton(response);
      
    } catch (error) {
      console.error('Job analysis failed:', error);
      this.showNotification('Job analysis failed: ' + error.message, 'error');
    }
  }

  async checkResumeUploaded() {
    try {
      // Check local storage first
      const localStorage = await chrome.storage.local.get(['resumeUploaded', 'resumeInfo']);
      if (localStorage.resumeUploaded && localStorage.resumeInfo) {
        return true;
      }
      
      // Fallback to checking backend
      const response = await fetch('http://localhost:8000/profile');
      const profile = await response.json();
      return !!(profile.base_resume_url);
    } catch (error) {
      console.error('Failed to check resume status:', error);
      // Check local storage as fallback
      const localStorage = await chrome.storage.local.get(['resumeUploaded']);
      return localStorage.resumeUploaded || false;
    }
  }

  showResumeUploadPrompt() {
    // Remove existing modal
    const existing = document.getElementById('ai-copilot-upload-modal');
    if (existing) existing.remove();
    
    const modal = document.createElement('div');
    modal.id = 'ai-copilot-upload-modal';
    modal.className = 'ai-copilot-modal';
    modal.innerHTML = `
      <div class="ai-copilot-modal-content">
        <div class="ai-copilot-modal-header">
          <h3>📄 Resume Required</h3>
          <button class="ai-copilot-close" onclick="this.closest('.ai-copilot-modal').remove()">×</button>
        </div>
        <div class="ai-copilot-modal-body">
          <p>To analyze job matches and tailor your applications, please upload your resume first.</p>
          <div class="ai-copilot-actions">
            <button class="ai-copilot-btn ai-copilot-btn-primary" id="ai-copilot-upload-btn">
              📤 Upload Resume
            </button>
            <button class="ai-copilot-btn ai-copilot-btn-secondary" onclick="this.closest('.ai-copilot-modal').remove()">
              Later
            </button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    // Wire event handler programmatically (inline handlers are blocked in MV3 isolated world)
    const uploadBtn = document.getElementById('ai-copilot-upload-btn');
    if (uploadBtn) {
      uploadBtn.addEventListener('click', () => this.openResumeUpload());
    }
  }

  async openResumeUpload() {
    // Create file input for resume upload
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.doc,.docx';
    input.style.display = 'none';
    
    input.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (file) {
        await this.uploadResume(file);
      }
    });
    
    document.body.appendChild(input);
    input.click();
    document.body.removeChild(input);
    
    // Close the modal
    const modal = document.getElementById('ai-copilot-upload-modal');
    if (modal) modal.remove();
  }

  async uploadResume(file) {
    try {
      this.showNotification('Uploading resume...', 'info');
      
      // Create FormData for multipart upload
      const formData = new FormData();
      formData.append('file', file);
      
      // Upload file using the new endpoint
      const response = await fetch('http://localhost:8000/upload-resume', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Upload failed: ${response.status} - ${errorText}`);
      }
      
      const result = await response.json();
      
      // Store resume info in extension storage
      const resumeInfo = {
        name: file.name,
        size: file.size,
        type: file.type,
        uploadDate: new Date().toISOString(),
        publicUrl: result.publicUrl
      };
      
      await chrome.storage.local.set({
        resumeUploaded: true,
        resumeInfo: resumeInfo
      });

      // Also set in backend profile so server recognizes base resume
      try {
        await fetch('http://localhost:8000/profile/base-resume', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: resumeInfo.publicUrl })
        });
      } catch (e) {
        console.warn('Failed to set base resume on backend (non-fatal):', e);
      }
      
      this.showNotification('Resume uploaded successfully!', 'success');
      
    } catch (error) {
      console.error('Resume upload failed:', error);
      this.showNotification('Resume upload failed: ' + error.message, 'error');
    }
  }

  addFloatingButton() {
    // Remove existing button
    const existing = document.getElementById('ai-copilot-button');
    if (existing) existing.remove();
    
    const button = document.createElement('div');
    button.id = 'ai-copilot-button';
    button.className = 'ai-copilot-floating-btn';
    button.innerHTML = `
      <div class="ai-copilot-btn-content">
        <span class="ai-copilot-icon">🤖</span>
        <span class="ai-copilot-text">AI Co-pilot</span>
      </div>
    `;
    
    button.addEventListener('click', () => this.showJobActions());
    
    document.body.appendChild(button);
  }

  updateFloatingButton(analysisData) {
    const button = document.getElementById('ai-copilot-button');
    if (button) {
      const matchScore = Math.round(analysisData.match_score * 100);
      button.innerHTML = `
        <div class="ai-copilot-btn-content">
          <span class="ai-copilot-icon">🎯</span>
          <span class="ai-copilot-text">${matchScore}% Match</span>
        </div>
      `;
    }
  }

  showJobActions() {
    // Remove existing modal
    const existing = document.getElementById('ai-copilot-modal');
    if (existing) existing.remove();
    
    const modal = document.createElement('div');
    modal.id = 'ai-copilot-modal';
    modal.className = 'ai-copilot-modal';
    modal.innerHTML = `
      <div class="ai-copilot-modal-content">
        <div class="ai-copilot-modal-header">
          <h3>AI Career Co-pilot</h3>
          <button class="ai-copilot-close" onclick="this.closest('.ai-copilot-modal').remove()">×</button>
        </div>
        <div class="ai-copilot-modal-body">
          ${this.currentJob ? `
            <h4>${this.currentJob.title}</h4>
            <p><strong>Company:</strong> ${this.currentJob.company}</p>
            <p><strong>ATS:</strong> ${this.currentJob.ats}</p>
            <div class="ai-copilot-actions">
              <button class="ai-copilot-btn ai-copilot-btn-primary" id="ai-copilot-analyze-btn">
                🔍 Analyze Job
              </button>
              <button class="ai-copilot-btn ai-copilot-btn-secondary" id="ai-copilot-tailor-btn">
                ✏️ Tailor Resume
              </button>
              <button class="ai-copilot-btn ai-copilot-btn-success" id="ai-copilot-fill-btn">
                📝 Auto-Fill Application
              </button>
            </div>
          ` : `
            <p>No job detected on this page.</p>
          `}
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close on outside click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
    // Wire button handlers
    const analyzeBtn = document.getElementById('ai-copilot-analyze-btn');
    if (analyzeBtn) analyzeBtn.addEventListener('click', () => this.analyzeCurrentJob());
    const tailorBtn = document.getElementById('ai-copilot-tailor-btn');
    if (tailorBtn) tailorBtn.addEventListener('click', () => this.tailorResume());
    const fillBtn = document.getElementById('ai-copilot-fill-btn');
    if (fillBtn) fillBtn.addEventListener('click', () => this.fillApplication());
  }

  async tailorResume() {
    if (!this.currentJob) return;
    
    try {
      this.showNotification('Tailoring resume with AI...', 'info');
      
      // First analyze if not done
      const storageKey = `analysis_${this.currentJob.url}`;
      let analysis = await chrome.storage.local.get(storageKey);
      
      if (!analysis[storageKey]) {
        await this.analyzeCurrentJob();
        analysis = await chrome.storage.local.get(storageKey);
      }
      
      const response = await chrome.runtime.sendMessage({
        action: 'tailorResume',
        data: {
          jobId: analysis[storageKey].job_id,
          constraints: {}
        }
      });
      
      if (response.error) {
        throw new Error(response.error);
      }
      
      this.showNotification('Resume tailored successfully!', 'success');
      
    } catch (error) {
      console.error('Resume tailoring failed:', error);
      this.showNotification('Resume tailoring failed: ' + error.message, 'error');
    }
  }

  async fillApplication() {
    if (!this.currentJob) return;
    
    try {
      this.showNotification('Filling application form...', 'info');
      
      const response = await chrome.runtime.sendMessage({
        action: 'fillForm',
        data: {
          jobId: this.currentJob.url,
          ats: this.currentJob.ats
        }
      });
      
      if (response.error) {
        throw new Error(response.error);
      }
      
      this.showNotification('Application form filled!', 'success');
      
    } catch (error) {
      console.error('Form filling failed:', error);
      this.showNotification('Form filling failed: ' + error.message, 'error');
    }
  }

  observePageChanges() {
    // For SPAs, detect URL changes
    let currentUrl = window.location.href;
    
    const observer = new MutationObserver(() => {
      if (window.location.href !== currentUrl) {
        currentUrl = window.location.href;
        setTimeout(() => this.detectJobPage(), 1000); // Give page time to load
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  showNotification(message, type = 'info') {
    // Remove existing notifications
    const existing = document.querySelectorAll('.ai-copilot-notification');
    existing.forEach(el => el.remove());
    
    const notification = document.createElement('div');
    notification.className = `ai-copilot-notification ai-copilot-notification-${type}`;
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

// Initialize job detector
const jobDetector = new JobDetector();
window.jobDetector = jobDetector; // Make it globally accessible
