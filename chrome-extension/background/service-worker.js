// AI Career Co-pilot Background Service Worker
const API_BASE = 'http://localhost:8000';
// OpenAI-compatible base for model tests (configurable via storage)
async function getAIBase() {
  const cfg = await chrome.storage.sync.get(['apiBase']);
  return (cfg.apiBase || 'http://localhost:11434/v1').replace(/\/$/, '');
}

// Install event
chrome.runtime.onInstalled.addListener(() => {
  console.log('AI Career Co-pilot installed');
  
  // Set default settings
  chrome.storage.sync.set({
    apiKey: '',
    aiModel: 'gpt-5',
    autoAnalyze: true,
    autoFill: true,
    constraints: {}
  });
});

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'analyzeJob':
      analyzeJobDescription(request.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true; // Keep message channel open for async response
      
    case 'tailorResume':
      tailorResume(request.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true;
      
    case 'fillForm':
      fillJobForm(request.data, sender.tab.id)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true;
      
    case 'trackOutcome':
      trackOutcome(request.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true;
  }
});

// Analyze job description using AI
async function analyzeJobDescription(data) {
  try {
    const response = await fetch(`${API_BASE}/ai/analyze-job`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_url: data.jobUrl,
        job_description: data.jobDescription
      })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    
    // Store analysis result
    chrome.storage.local.set({
      [`analysis_${data.jobUrl}`]: result
    });
    
    return result;
  } catch (error) {
    console.error('Job analysis failed:', error);
    throw error;
  }
}

// Tailor resume using AI
async function tailorResume(data) {
  try {
    const response = await fetch(`${API_BASE}/ai/tailor-resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_id: data.jobId,
        user_constraints: data.constraints
      })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    
    // Store tailored resume
    chrome.storage.local.set({
      [`resume_${data.jobId}`]: result
    });
    
    return result;
  } catch (error) {
    console.error('Resume tailoring failed:', error);
    throw error;
  }
}

// Fill job application form
async function fillJobForm(data, tabId) {
  try {
    // Get tailored resume data
    const storageKey = `resume_${data.jobId}`;
    const storage = await chrome.storage.local.get(storageKey);
    const resumeData = storage[storageKey];
    
    if (!resumeData) {
      throw new Error('No tailored resume found. Please analyze and tailor first.');
    }
    
    // Inject form filler script
    await chrome.scripting.executeScript({
      target: { tabId: tabId },
      function: fillFormFields,
      args: [resumeData.tailored_resume]
    });
    
    return { success: true };
  } catch (error) {
    console.error('Form filling failed:', error);
    throw error;
  }
}

// Function to be injected into page for form filling
function fillFormFields(resumeData) {
  // This function runs in the page context
  const fields = {
    // Personal Information
    name: resumeData.name,
    email: resumeData.contact?.email,
    phone: resumeData.contact?.phone,
    location: resumeData.contact?.location,
    linkedin: resumeData.contact?.linkedin,
    github: resumeData.contact?.github,
    
    // Professional
    summary: resumeData.summary,
    experience: resumeData.experience,
    skills: resumeData.skills,
    education: resumeData.education
  };
  
  // Common field selectors for different ATS platforms
  const selectors = {
    firstName: ['input[name*="first"], input[name*="fname"], input[placeholder*="First"]'],
    lastName: ['input[name*="last"], input[name*="lname"], input[placeholder*="Last"]'],
    email: ['input[type="email"], input[name*="email"], input[placeholder*="email"]'],
    phone: ['input[type="tel"], input[name*="phone"], input[placeholder*="phone"]'],
    location: ['input[name*="location"], input[name*="city"], input[placeholder*="location"]'],
    linkedin: ['input[name*="linkedin"], input[placeholder*="linkedin"]'],
    github: ['input[name*="github"], input[placeholder*="github"]'],
    website: ['input[name*="website"], input[name*="portfolio"]'],
    coverLetter: ['textarea[name*="cover"], textarea[placeholder*="cover"]'],
    summary: ['textarea[name*="summary"], textarea[placeholder*="summary"]'],
    experience: ['textarea[name*="experience"], textarea[placeholder*="experience"]']
  };
  
  // Fill basic fields
  if (fields.name) {
    const nameParts = fields.name.split(' ');
    fillField(selectors.firstName, nameParts[0]);
    fillField(selectors.lastName, nameParts.slice(1).join(' '));
  }
  
  fillField(selectors.email, fields.email);
  fillField(selectors.phone, fields.phone);
  fillField(selectors.location, fields.location);
  fillField(selectors.linkedin, fields.linkedin);
  fillField(selectors.github, fields.github);
  fillField(selectors.summary, fields.summary);
  
  // Helper function to fill fields
  function fillField(selectorArray, value) {
    if (!value) return;
    
    for (const selector of selectorArray) {
      const elements = document.querySelectorAll(selector);
      for (const element of elements) {
        if (element && !element.value) {
          element.value = value;
          element.dispatchEvent(new Event('input', { bubbles: true }));
          element.dispatchEvent(new Event('change', { bubbles: true }));
          return; // Fill only the first empty field
        }
      }
    }
  }
  
  // Show success notification
  showNotification('Form filled with AI-tailored data!', 'success');
}

// Track application outcome
async function trackOutcome(data) {
  try {
    const response = await fetch(`${API_BASE}/ai/track-outcome`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Outcome tracking failed:', error);
    throw error;
  }
}

// Show notification
function showNotification(message, type = 'info') {
  // This would be implemented in content script
  console.log(`[${type.toUpperCase()}] ${message}`);
}
