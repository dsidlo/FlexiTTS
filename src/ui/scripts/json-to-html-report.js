#!/usr/bin/env node
/**
 * Converts Vitest JSON test results to HTML report
 * Usage: node json-to-html-report.js [input.json] [output.html]
 */

import fs from 'fs';
import path from 'path';

const inputFile = process.argv[2] || './test-reports/test-results.json';
const outputFile = process.argv[3] || './test-reports/test-results.html';

if (!fs.existsSync(inputFile)) {
  console.error(`Error: ${inputFile} not found`);
  console.log('Run tests first: npm run test:report');
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));

const startTime = new Date(data.startTime).toLocaleString();
const duration = ((data.endTime - data.startTime) / 1000).toFixed(2);

// Calculate success rate
const successRate = Math.round((data.numPassedTests / data.numTotalTests) * 100);

// Generate test file cards
const testFilesHtml = data.testResults.map(result => {
  const fileName = result.name.split('/').pop();
  const passed = result.assertionResults.filter(a => a.status === 'passed').length;
  const failed = result.assertionResults.filter(a => a.status === 'failed').length;
  const total = result.assertionResults.length;
  const status = failed === 0 ? 'passed' : 'failed';
  
  const testsList = result.assertionResults.map(test => {
    const icon = test.status === 'passed' ? '✓' : '✗';
    const statusClass = test.status === 'passed' ? 'test-pass' : 'test-fail';
    const duration = test.duration ? `(${test.duration}ms)` : '';
    return `<div class="test-item ${statusClass}">${icon} ${test.title} ${duration}</div>`;
  }).join('');
  
  return `
    <div class="test-file ${status}">
      <div class="file-header">
        <h3>${fileName}</h3>
        <span class="file-stats">${passed}/${total} passed</span>
      </div>
      <div class="tests-list">
        ${testsList}
      </div>
    </div>
  `;
}).join('');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FlexiTTS Test Results</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
      padding: 20px;
      line-height: 1.6;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    header {
      background: white;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      margin-bottom: 20px;
    }
    h1 { color: #333; margin-bottom: 10px; }
    .nav-banner {
      background: #3b82f6;
      color: white;
      padding: 12px 20px;
      text-align: center;
      margin: -30px -30px 20px -30px;
      border-radius: 8px 8px 0 0;
    }
    .nav-banner a {
      color: white;
      text-decoration: none;
      font-weight: 500;
    }
    .nav-banner a:hover {
      text-decoration: underline;
    }
    .meta { color: #666; font-size: 14px; }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin: 20px 0;
    }
    .summary-card {
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      text-align: center;
    }
    .summary-card h2 {
      font-size: 36px;
      margin-bottom: 5px;
    }
    .summary-card.passed h2 { color: #22c55e; }
    .summary-card.failed h2 { color: #ef4444; }
    .summary-card.total h2 { color: #3b82f6; }
    .summary-card.rate h2 { color: #8b5cf6; }
    .summary-card p { color: #666; font-size: 14px; }
    .test-files {
      display: grid;
      gap: 15px;
    }
    .test-file {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      overflow: hidden;
    }
    .test-file.passed { border-left: 4px solid #22c55e; }
    .test-file.failed { border-left: 4px solid #ef4444; }
    .file-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px 20px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
    }
    .file-header h3 { color: #333; font-size: 16px; }
    .file-stats {
      background: #e5e7eb;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      color: #666;
    }
    .tests-list {
      padding: 15px 20px;
    }
    .test-item {
      padding: 10px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 14px;
    }
    .test-item:last-child { border-bottom: none; }
    .test-pass { color: #22c55e; }
    .test-fail { color: #ef4444; }
    .footer {
      margin-top: 30px;
      padding: 20px;
      text-align: center;
      color: #666;
      font-size: 12px;
    }
    .nav-links {
      margin-top: 15px;
    }
    .nav-links a {
      color: #3b82f6;
      text-decoration: none;
      margin: 0 10px;
    }
    .nav-links a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="nav-banner">
        <a href="coverage/index.html">📊 View Coverage Report →</a>
      </div>
      <h1>🧪 FlexiTTS Test Results</h1>
      <div class="meta">
        <p>Started: ${startTime}</p>
        <p>Duration: ${duration}s</p>
      </div>
    </header>
    
    <div class="summary">
      <div class="summary-card total">
        <h2>${data.numTotalTests}</h2>
        <p>Total Tests</p>
      </div>
      <div class="summary-card passed">
        <h2>${data.numPassedTests}</h2>
        <p>Passed</p>
      </div>
      <div class="summary-card failed">
        <h2>${data.numFailedTests}</h2>
        <p>Failed</p>
      </div>
      <div class="summary-card rate">
        <h2>${successRate}%</h2>
        <p>Success Rate</p>
      </div>
    </div>
    
    <div class="test-files">
      ${testFilesHtml}
    </div>
    
    <footer>
      <div class="nav-links">
        <a href="coverage/index.html">View Coverage Report →</a>
        <a href="test-results.json">View JSON Data</a>
      </div>
      <p>Generated by Vitest • FlexiTTS UI Tests</p>
    </footer>
  </div>
</body>
</html>`;

fs.writeFileSync(outputFile, html);
console.log(`✅ HTML report generated: ${outputFile}`);
console.log(`📊 Summary: ${data.numPassedTests}/${data.numTotalTests} tests passed (${successRate}%)`);
