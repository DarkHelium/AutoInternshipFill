// AI Career Co-pilot Popup Script
class PopupController {
  constructor() {
    this.currentTab = null;
    this.currentJob = null;
    this.init();
  }

  async init() {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    this.currentTab = tab;
    
    // Load settings
    await this.loadSettings();
    
    // Check for job on current page
    await this.checkCurrentPage();
    
    // Setup event listeners
    this.setupEventListeners();
    
    // Update UI
    this.updateUI();
  }

  async loadSettings() {
    const settings = await chrome.storage.sync.get([
      'apiKey', 'aiModel', 'autoAnalyze', 'autoFill'
    ]);
    
    document.getElementById('ai-model').textContent = settings.aiModel || 'GPT-5';
  }

  async checkCurrentPage() {
    try {
      // Inject content script to check for job
      const results = await chrome.scripting.executeScript({
        target: { tabId: this.currentTab.id },
        function: () => {
          return window.jobDetector ? window.jobDetector.currentJob : null;
        }
      });
      
      if (results && results[0] && results[0].result) {
        this.currentJob = results[0].result;
        document.getElementById('current-job').textContent = 
          `${this.currentJob.title} at ${this.currentJob.company}`;
        
        // Check if analysis exists
        const storageKey = `analysis_${this.currentJob.url}`;
        const analysis = await chrome.storage.local.get(storageKey);
        
        if (analysis[storageKey]) {
          this.updateMatchScore(analysis[storageKey].match_score);
          // If already analyzed, hide or disable Analyze
          const analyzeBtn = document.getElementById('analyze-btn');
          analyzeBtn.disabled = true;
          analyzeBtn.textContent = 'Analyzed';
          // Enable Tailor
          document.getElementById('tailor-btn').disabled = false;
        } else {
          // Enable Analyze if no analysis yet
          document.getElementById('analyze-btn').disabled = false;
        }
      }
    } catch (error) {
      console.error('Failed to check current page:', error);
      this.showError('Failed to detect job on current page');
    }
  }

  setupEventListeners() {
    // Analyze button
    document.getElementById('analyze-btn').addEventListener('click', () => {
      this.analyzeJob();
    });
    
    // Tailor button
    document.getElementById('tailor-btn').addEventListener('click', () => {
      this.tailorResume();
    });
    
    // Fill button
    document.getElementById('fill-btn').addEventListener('click', () => {
      this.fillForm();
    });
    
    // Preview button
    document.getElementById('preview-btn').addEventListener('click', () => {
      this.showATSPreview();
    });
    
    // Settings link
    document.getElementById('settings-link').addEventListener('click', (e) => {
      e.preventDefault();
      chrome.runtime.openOptionsPage();
    });
  }

  async analyzeJob() {
    if (!this.currentJob) return;
    
    this.showLoading('Analyzing job with AI...');
    
    try {
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
      
      this.updateMatchScore(response.match_score);
      document.getElementById('tailor-btn').disabled = false;
      
      this.hideLoading();
      this.showSuccess('Job analyzed successfully!');
      
    } catch (error) {
      this.hideLoading();
      this.showError('Analysis failed: ' + error.message);
    }
  }

  async tailorResume() {
    if (!this.currentJob) return;
    
    this.showLoading('Tailoring resume with AI...');
    
    try {
      // Get analysis first
      const storageKey = `analysis_${this.currentJob.url}`;
      const analysis = await chrome.storage.local.get(storageKey);
      
      if (!analysis[storageKey]) {
        throw new Error('Please analyze the job first');
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
      
      document.getElementById('fill-btn').disabled = false;
      document.getElementById('preview-btn').disabled = false;
      // Mark Tailor as completed
      const tailorBtn = document.getElementById('tailor-btn');
      tailorBtn.disabled = true;
      tailorBtn.textContent = 'Tailored';
      
      this.hideLoading();
      this.showSuccess('Resume tailored successfully!');
      
    } catch (error) {
      this.hideLoading();
      this.showError('Tailoring failed: ' + error.message);
    }
  }

  async fillForm() {
    if (!this.currentJob) return;
    
    this.showLoading('Filling application form...');
    
    try {
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
      
      this.hideLoading();
      this.showSuccess('Form filled successfully!');
      
      // Close popup after successful fill
      setTimeout(() => window.close(), 2000);
      
    } catch (error) {
      this.hideLoading();
      this.showError('Form filling failed: ' + error.message);
    }
  }

  async showATSPreview() {
    if (!this.currentJob) return;
    
    try {
      // Get analysis to find job_id
      const storageKey = `analysis_${this.currentJob.url}`;
      const analysis = await chrome.storage.local.get(storageKey);
      
      if (!analysis[storageKey]) {
        throw new Error('Please analyze and tailor resume first');
      }
      
      // Open new tab with ATS preview
      chrome.tabs.create({
        url: `http://localhost:8000/ai/ats-preview?job_id=${analysis[storageKey].job_id}`
      });
      
    } catch (error) {
      this.showError('Preview failed: ' + error.message);
    }
  }

  updateMatchScore(score) {
    const matchCard = document.getElementById('match-card');
    const matchScore = document.getElementById('match-score');
    
    const percentage = Math.round(score * 100);
    matchScore.textContent = `${percentage}%`;
    
    // Update color based on score
    matchScore.className = 'match-score';
    if (percentage >= 70) {
      matchScore.classList.add('high');
    } else if (percentage >= 40) {
      matchScore.classList.add('medium');
    } else {
      matchScore.classList.add('low');
    }
    
    matchCard.style.display = 'block';
  }

  showLoading(message) {
    document.getElementById('main-content').style.display = 'none';
    document.getElementById('loading').style.display = 'block';
    document.querySelector('#loading p').textContent = message;
  }

  hideLoading() {
    document.getElementById('main-content').style.display = 'block';
    document.getElementById('loading').style.display = 'none';
  }

  showError(message) {
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    
    setTimeout(() => {
      errorEl.style.display = 'none';
    }, 5000);
  }

  showSuccess(message) {
    // Reuse error styling but with different color
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.style.background = 'rgba(40, 167, 69, 0.2)';
    errorEl.style.borderColor = 'rgba(40, 167, 69, 0.5)';
    errorEl.style.display = 'block';
    
    setTimeout(() => {
      errorEl.style.display = 'none';
      errorEl.style.background = 'rgba(220, 53, 69, 0.2)';
      errorEl.style.borderColor = 'rgba(220, 53, 69, 0.5)';
    }, 3000);
  }

  updateUI() {
    // Enable/disable buttons based on state
    if (!this.currentJob) {
      document.getElementById('current-job').textContent = 'No job detected on this page';
      return;
    }
  }
}

// Initialize popup
document.addEventListener('DOMContentLoaded', () => {
  new PopupController();
});
