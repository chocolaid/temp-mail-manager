const express = require('express');
const puppeteer = require('puppeteer');
const fs = require('fs-extra');
const path = require('path');
const rateLimit = require('express-rate-limit');
const winston = require('winston');
const helmet = require('helmet');
const { v4: uuidv4 } = require('uuid');

const app = express();
const port = process.env.PORT || 3000;

// Configuration
const config = {
  browserTimeout: 30000,
  maxSessions: 100,
  cleanupInterval: 3600000,
  sessionLifetime: 86400000,
  isProduction: process.env.NODE_ENV === 'production'
};

// Setup logging
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

if (!config.isProduction) {
  logger.add(new winston.transports.Console({
    format: winston.format.simple()
  }));
}

// Security middleware
app.use(helmet());
app.use(express.json());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 200
});
app.use(limiter);

// Browser management
class BrowserManager {
  constructor() {
    this.browsers = new Map();
  }

  async launchBrowser(sessionId) {
    try {
      logger.info('Launching browser', { sessionId });
      
      const browser = await puppeteer.launch({
        headless: config.isProduction ? 'new' : false,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--window-size=1280,720'
        ],
        timeout: config.browserTimeout
      });
      
      this.browsers.set(sessionId, browser);
      return browser;
    } catch (error) {
      logger.error('Failed to launch browser', { error: error.message });
      throw error;
    }
  }

  async getBrowser(sessionId) {
    return this.browsers.get(sessionId);
  }

  async closeBrowser(sessionId) {
    const browser = this.browsers.get(sessionId);
    if (browser) {
      try {
        await browser.close();
        this.browsers.delete(sessionId);
        logger.info('Browser closed', { sessionId });
      } catch (error) {
        logger.error('Failed to close browser', { sessionId, error: error.message });
      }
    }
  }

  async cleanupOldSessions() {
    try {
      const now = Date.now();
      for (const [sessionId, browser] of this.browsers.entries()) {
        try {
          await browser.close();
          this.browsers.delete(sessionId);
          logger.info('Cleaned up old session', { sessionId });
        } catch (error) {
          logger.error('Failed to cleanup session', { sessionId, error: error.message });
        }
      }
    } catch (error) {
      logger.error('Failed to cleanup sessions', { error: error.message });
    }
  }
}

const browserManager = new BrowserManager();

// Start cleanup interval
setInterval(() => browserManager.cleanupOldSessions(), config.cleanupInterval);

// Create a new temp email
app.get('/create-email', async (req, res) => {
  try {
    const sessionId = uuidv4();
    logger.info('Creating new email session', { sessionId });
    
    const browser = await browserManager.launchBrowser(sessionId);
    const page = await browser.newPage();
    
    logger.info('Navigating to temp-mail.io');
    await page.goto('https://temp-mail.io/en', { 
      waitUntil: 'networkidle0',
      timeout: config.browserTimeout 
    });

    logger.info('Waiting for email input field');
    await page.waitForSelector('input#email', { timeout: config.browserTimeout });
    
    logger.info('Extracting email address');
    const email = await page.$eval('input#email', el => el.value);
    logger.info('Email address found', { email });
    
    logger.info('Created new email', { sessionId, email });
    res.json({ sessionId, email });
  } catch (error) {
    logger.error('Failed to create email', { error: error.message });
    res.status(500).json({ error: 'Failed to create email' });
  }
});

// Get inbox for a session
app.get('/get-inbox/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const browser = await browserManager.getBrowser(sessionId);

    if (!browser) {
      return res.status(404).json({ error: 'Session not found' });
    }

    const page = await browser.newPage();
    await page.goto('https://temp-mail.io/en', { 
      waitUntil: 'networkidle0',
      timeout: config.browserTimeout 
    });

    await page.waitForTimeout(3000);

    const inboxItems = await page.evaluate(() => {
      const emails = [];
      const items = document.querySelectorAll('ul.email-list > li.message');
      items.forEach(item => {
        const from = item.querySelector('div.truncate')?.innerText.trim() || '';
        const date = item.querySelector('span[data-qa="date"]')?.innerText.trim() || '';
        const subject = item.querySelector('span[data-qa="message-subject"]')?.innerText.trim() || '';
        const snippet = item.querySelector('div.message__body')?.innerText.trim() || '';
        
        emails.push({ from, date, subject, snippet });
      });
      return emails;
    });

    await page.close();
    
    logger.info('Retrieved inbox', { sessionId, emailCount: inboxItems.length });
    res.json({ inbox: inboxItems });
  } catch (error) {
    logger.error('Failed to get inbox', { sessionId: req.params.sessionId, error: error.message });
    res.status(500).json({ error: 'Failed to retrieve inbox' });
  }
});

// Kill a session (supports both GET and POST)
app.route('/kill-session/:sessionId')
  .get(async (req, res) => {
    try {
      const { sessionId } = req.params;
      await browserManager.closeBrowser(sessionId);
      res.json({ message: 'Session killed successfully' });
    } catch (error) {
      logger.error('Failed to kill session', { sessionId: req.params.sessionId, error: error.message });
      res.status(500).json({ error: 'Failed to kill session' });
    }
  })
  .post(async (req, res) => {
    try {
      const { sessionId } = req.params;
      await browserManager.closeBrowser(sessionId);
      res.json({ message: 'Session killed successfully' });
    } catch (error) {
      logger.error('Failed to kill session', { sessionId: req.params.sessionId, error: error.message });
      res.status(500).json({ error: 'Failed to kill session' });
    }
  });

// Error handling middleware
app.use((err, req, res, next) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).json({ error: 'Internal server error' });
});

// Health check endpoint for Railway
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start server
const server = app.listen(port, '0.0.0.0', () => {
  logger.info(`Server running on port ${port}`);
});

// Handle graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM signal received. Closing HTTP server...');
  server.close(() => {
    logger.info('HTTP server closed');
    process.exit(0);
  });
});
