// AI Career Co-pilot Options Script
class OptionsController {
  constructor() {
    this.init();
  }

  async init() {
    await this.loadSettings();
    this.setupEventListeners();
  }

  async loadSettings() {
    try {
      const settings = await chrome.storage.sync.get([
        'apiKey', 'aiModel', 'apiBase', 'autoAnalyze', 'autoFill', 'showNotifications',
        'preferredLocations', 'remoteOnly', 'salaryMin', 'salaryMax',
        'dealbreakers', 'preferences', 'experienceLevel', 'targetRoles'
      ]);
      
      // Load resume info
      const resumeData = await chrome.storage.local.get(['resumeFile', 'resumeInfo']);
      if (resumeData.resumeInfo) {
        this.displayResumeInfo(resumeData.resumeInfo);
      }
      
      // API Settings
      document.getElementById('api-key').value = settings.apiKey || '';
      document.getElementById('ai-model').value = settings.aiModel || 'gpt-5';
      document.getElementById('api-base').value = settings.apiBase || 'http://localhost:11434/v1';
      
      // Automation Settings
      document.getElementById('auto-analyze').checked = settings.autoAnalyze !== false;
      document.getElementById('auto-fill').checked = settings.autoFill !== false;
      document.getElementById('show-notifications').checked = settings.showNotifications !== false;
      
      // Career Constraints
      document.getElementById('preferred-locations').value = settings.preferredLocations || '';
      document.getElementById('remote-only').checked = settings.remoteOnly || false;
      document.getElementById('salary-min').value = settings.salaryMin || '';
      document.getElementById('salary-max').value = settings.salaryMax || '';
      document.getElementById('dealbreakers').value = settings.dealbreakers || '';
      document.getElementById('preferences').value = settings.preferences || '';
      
      // Profile Info
      document.getElementById('experience-level').value = settings.experienceLevel || 'mid';
      document.getElementById('target-roles').value = settings.targetRoles || '';
      
    } catch (error) {
      console.error('Failed to load settings:', error);
      this.showStatus('Failed to load settings', 'error');
    }
  }

  setupEventListeners() {
    // Auto-save on input changes
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
      input.addEventListener('change', () => {
        // Debounce auto-save
        clearTimeout(this.autoSaveTimeout);
        this.autoSaveTimeout = setTimeout(() => this.autoSave(), 1000);
      });
    });
  }

  async autoSave() {
    try {
      await this.saveSettings(false); // Don't show status for auto-save
    } catch (error) {
      console.error('Auto-save failed:', error);
    }
  }

  async saveSettings(showStatus = true) {
    try {
      const settings = {
        // API Settings
        apiKey: document.getElementById('api-key').value.trim(),
        aiModel: document.getElementById('ai-model').value,
        apiBase: document.getElementById('api-base').value.trim(),
        
        // Automation Settings
        autoAnalyze: document.getElementById('auto-analyze').checked,
        autoFill: document.getElementById('auto-fill').checked,
        showNotifications: document.getElementById('show-notifications').checked,
        
        // Career Constraints
        preferredLocations: document.getElementById('preferred-locations').value.trim(),
        remoteOnly: document.getElementById('remote-only').checked,
        salaryMin: parseInt(document.getElementById('salary-min').value) || null,
        salaryMax: parseInt(document.getElementById('salary-max').value) || null,
        dealbreakers: document.getElementById('dealbreakers').value.trim(),
        preferences: document.getElementById('preferences').value.trim(),
        
        // Profile Info
        experienceLevel: document.getElementById('experience-level').value,
        targetRoles: document.getElementById('target-roles').value.trim()
      };
      
      await chrome.storage.sync.set(settings);
      
      // Also update profile in backend if API key is set
      if (settings.apiKey) {
        await this.updateBackendProfile(settings);
      }
      
      if (showStatus) {
        this.showStatus('Settings saved successfully!', 'success');
      }
      
    } catch (error) {
      console.error('Failed to save settings:', error);
      this.showStatus('Failed to save settings: ' + error.message, 'error');
    }
  }

  async updateBackendProfile(settings) {
    try {
      const profileData = {
        ai_api_key: settings.apiKey,
        preferred_ai_model: settings.aiModel,
        experience_level: settings.experienceLevel,
        target_roles: settings.targetRoles ? settings.targetRoles.split(',').map(r => r.trim()) : [],
        career_constraints: {
          preferred_locations: settings.preferredLocations ? settings.preferredLocations.split(',').map(l => l.trim()) : [],
          remote_only: settings.remoteOnly,
          dealbreakers: settings.dealbreakers,
          preferences: settings.preferences
        },
        salary_expectations: {
          min: settings.salaryMin,
          max: settings.salaryMax,
          currency: 'USD'
        },
        location_preferences: {
          remote_ok: !settings.remoteOnly, // If remote-only is false, remote is still ok
          remote_only: settings.remoteOnly,
          preferred_locations: settings.preferredLocations ? settings.preferredLocations.split(',').map(l => l.trim()) : []
        }
      };
      
      const response = await fetch('http://localhost:8000/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profileData)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
    } catch (error) {
      console.error('Failed to update backend profile:', error);
      // Don't show error to user as this is optional
    }
  }

  async testConnection() {
    const apiKey = document.getElementById('api-key').value.trim();
    
    if (!apiKey) {
      this.showStatus('Please enter your API key first', 'error');
      return;
    }
    
    this.showStatus('Testing API connection...', 'info');
    
    try {
      const cfg = await chrome.storage.sync.get(['apiBase']);
      const apiBase = (cfg.apiBase || 'http://localhost:11434/v1').replace(/\/$/, '');
      const response = await fetch(`${apiBase}/models`, {
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        this.showStatus('API connection successful! ✅', 'success');
      } else {
        throw new Error(`API returned ${response.status}`);
      }
      
    } catch (error) {
      console.error('API test failed:', error);
      this.showStatus('API connection failed: ' + error.message, 'error');
    }
  }

  async exportData() {
    try {
      // Get all stored data
      const syncData = await chrome.storage.sync.get();
      const localData = await chrome.storage.local.get();
      
      const exportData = {
        settings: syncData,
        data: localData,
        exportDate: new Date().toISOString(),
        version: '1.0.0'
      };
      
      // Create download
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-career-copilot-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      this.showStatus('Data exported successfully!', 'success');
      
    } catch (error) {
      console.error('Export failed:', error);
      this.showStatus('Export failed: ' + error.message, 'error');
    }
  }

  async clearData() {
    if (!confirm('Are you sure you want to clear all data? This cannot be undone.')) {
      return;
    }
    
    try {
      await chrome.storage.sync.clear();
      await chrome.storage.local.clear();
      
      // Reset form
      document.querySelector('form').reset();
      
      this.showStatus('All data cleared successfully!', 'success');
      
    } catch (error) {
      console.error('Clear data failed:', error);
      this.showStatus('Failed to clear data: ' + error.message, 'error');
    }
  }

  showStatus(message, type = 'info') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
    statusEl.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
      statusEl.style.display = 'none';
    }, 5000);
  }

  async uploadResume() {
    const fileInput = document.getElementById('resume-upload');
    const file = fileInput.files[0];
    
    if (!file) {
      this.showStatus('Please select a resume file', 'error');
      return;
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB limit
      this.showStatus('File too large. Please select a file under 10MB', 'error');
      return;
    }
    
    try {
      this.showStatus('Uploading resume...', 'info');
      
      // Convert file to base64 for storage
      const base64 = await this.fileToBase64(file);
      
      // Store resume data
      const resumeInfo = {
        name: file.name,
        size: file.size,
        type: file.type,
        uploadDate: new Date().toISOString()
      };
      
      await chrome.storage.local.set({
        resumeFile: base64,
        resumeInfo: resumeInfo
      });
      
      // Also upload to backend
      await this.uploadToBackend(file);
      
      this.displayResumeInfo(resumeInfo);
      this.showStatus('Resume uploaded successfully!', 'success');
      
      // Clear file input
      fileInput.value = '';
      
    } catch (error) {
      console.error('Resume upload failed:', error);
      this.showStatus('Upload failed: ' + error.message, 'error');
    }
  }

  async uploadToBackend(file) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch('http://localhost:8000/upload-resume', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`Backend upload failed: ${response.status}`);
      }
      
    } catch (error) {
      console.error('Backend upload failed:', error);
      // Don't fail the whole upload if backend is unavailable
    }
  }

  fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  }

  displayResumeInfo(resumeInfo) {
    const currentResumeEl = document.getElementById('current-resume');
    const resumeNameEl = document.getElementById('resume-name');
    const resumeDateEl = document.getElementById('resume-date');
    
    resumeNameEl.textContent = resumeInfo.name;
    resumeDateEl.textContent = `Uploaded: ${new Date(resumeInfo.uploadDate).toLocaleDateString()}`;
    currentResumeEl.style.display = 'block';
  }

  async removeResume() {
    if (!confirm('Are you sure you want to remove your uploaded resume?')) {
      return;
    }
    
    try {
      await chrome.storage.local.remove(['resumeFile', 'resumeInfo']);
      document.getElementById('current-resume').style.display = 'none';
      this.showStatus('Resume removed successfully!', 'success');
      
    } catch (error) {
      console.error('Failed to remove resume:', error);
      this.showStatus('Failed to remove resume: ' + error.message, 'error');
    }
  }
}

// Global functions for HTML onclick handlers
function toggleApiKey() {
  const input = document.getElementById('api-key');
  const button = document.querySelector('.api-key-toggle');
  
  if (input.type === 'password') {
    input.type = 'text';
    button.textContent = 'Hide';
  } else {
    input.type = 'password';
    button.textContent = 'Show';
  }
}

function saveSettings() {
  window.optionsController.saveSettings();
}

function testConnection() {
  window.optionsController.testConnection();
}

function exportData() {
  window.optionsController.exportData();
}

function clearData() {
  window.optionsController.clearData();
}

function uploadResume() {
  window.optionsController.uploadResume();
}

function removeResume() {
  window.optionsController.removeResume();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.optionsController = new OptionsController();
});
