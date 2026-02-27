#!/usr/bin/env node
/**
 * Inject Dark Theme CSS into Vitest Coverage Reports
 * Usage: node inject-coverage-dark-theme.js [coverage-dir]
 * 
 * Adds dark theme support to @vitest/coverage-v8 (c8) HTML reports
 */

import fs from 'fs';
import path from 'path';

const coverageDir = process.argv[2] || './test-reports/coverage';

if (!fs.existsSync(coverageDir)) {
  console.error(`❌ Coverage directory not found: ${coverageDir}`);
  console.log('Run tests with coverage first: npm run test:coverage');
  process.exit(1);
}

console.log('🎨 Injecting dark theme into coverage reports...');

// Dark theme CSS to inject into base.css
const darkThemeCSS = `
/* === DARK THEME OVERRIDES === */
body {
  background: #1a1a2e !important;
  color: #eaeaea !important;
}

.wrapper {
  background: #1a1a2e !important;
}

h1, h2 {
  color: #eaeaea !important;
}

.coverage-summary {
  border: 1px solid #0f3460 !important;
}

.coverage-summary tr {
  border-bottom: 1px solid #0f3460 !important;
}

.coverage-summary th {
  background: #16213e !important;
  color: #eaeaea !important;
}

.coverage-summary td {
  border-right: 1px solid #0f3460 !important;
  color: #eaeaea !important;
}

.coverage-summary tbody {
  border: 1px solid #0f3460 !important;
}

.coverage-summary tbody tr:nth-child(even) {
  background: #16213e !important;
}

.coverage-summary tbody tr:nth-child(odd) {
  background: #1a1a2e !important;
}

.coverage-summary tbody tr:hover {
  background: #0f3460 !important;
}

table.coverage td.line-count {
  background: #16213e !important;
  color: #a0a0a0 !important;
}

/* Coverage colors adjusted for dark theme */
.high .cover-fill { background: #4ade80 !important; }
.high { color: #4ade80 !important; }
.medium .cover-fill { background: #facc15 !important; }
.medium { color: #facc15 !important; }
.low .cover-fill { background: #f87171 !important; }
.low { color: #f87171 !important; }

/* Line coverage indicators */
.cline-yes { background: rgba(74, 222, 128, 0.3) !important; color: #eaeaea !important; }
.cline-no { background: rgba(248, 113, 113, 0.3) !important; color: #eaeaea !important; }
.cline-neutral { background: rgba(160, 160, 160, 0.2) !important; color: #a0a0a0 !important; }

/* Quiet/secondary text */
.quiet {
  color: #a0a0a0 !important;
}

.quiet a {
  color: #4fc3f7 !important;
}

.quiet a:hover {
  color: #80d8ff !important;
}

/* Fraction display */
.fraction {
  background: #16213e !important;
  color: #eaeaea !important;
}

/* Links */
a { color: #4fc3f7 !important; }
a:hover { color: #80d8ff !important; }

/* Stats badges */
.strong { color: #4ade80 !important; }

/* Filter input */
#fileSearch {
  background: #16213e !important;
  color: #eaeaea !important;
  border: 1px solid #0f3460 !important;
  padding: 5px 10px;
  border-radius: 4px;
}

#fileSearch::placeholder {
  color: #a0a0a0 !important;
}

/* Pad/spacing backgrounds */
.pad1, .pad2 {
  background: transparent !important;
}

/* Footer */
.footer {
  background: #16213e !important;
  border-top: 1px solid #0f3460 !important;
  color: #a0a0a0 !important;
}

/* Pre/code blocks */
pre.prettyprint {
  background: #16213e !important;
  color: #eaeaea !important;
}

/* Coverage chart fills */
.cover-fill { opacity: 0.8; }
.cover-empty { background: #0f3460 !important; }

/* Branch coverage */
.missing-if-branch {
  background: #facc15 !important;
  color: #111 !important;
}

.skip-if-branch {
  background: #16213e !important;
  color: #a0a0a0 !important;
}

/* Status lines */
.status-line { opacity: 0.9; }
`;

// Inject dark theme into base.css
const baseCssPath = path.join(coverageDir, 'base.css');
if (fs.existsSync(baseCssPath)) {
  let baseCss = fs.readFileSync(baseCssPath, 'utf-8');
  
  // Check if already injected
  if (!baseCss.includes('DARK THEME OVERRIDES')) {
    baseCss += darkThemeCSS;
    fs.writeFileSync(baseCssPath, baseCss);
    console.log('✅ Dark theme injected into base.css');
  } else {
    console.log('ℹ️ Dark theme already present in base.css');
  }
} else {
  console.warn('⚠️ base.css not found');
}

// Update index.html to add a banner
const indexHtmlPath = path.join(coverageDir, 'index.html');
if (fs.existsSync(indexHtmlPath)) {
  let indexHtml = fs.readFileSync(indexHtmlPath, 'utf-8');
  
  // Add nav banner after <h1> if not already present
  if (!indexHtml.includes('coverage-nav-banner')) {
    indexHtml = indexHtml.replace(
      /<h1>All files<\/h1>/,
      `<h1>All files</h1>
    <div id="coverage-nav-banner" style="background: #3b82f6; color: white; padding: 10px 20px; margin: 10px -20px 20px -20px; text-align: center;">
      <a href="../test-results.html" style="color: white; text-decoration: none; font-weight: 500;">← Back to Test Results</a>
    </div>`
    );
    fs.writeFileSync(indexHtmlPath, indexHtml);
    console.log('✅ Navigation banner added to index.html');
  } else {
    console.log('ℹ️ Navigation banner already present');
  }
}

// Find all other HTML files and inject dark theme
const htmlFiles = [];
function findHtmlFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      findHtmlFiles(fullPath);
    } else if (entry.name.endsWith('.html')) {
      htmlFiles.push(fullPath);
    }
  }
}

findHtmlFiles(coverageDir);

let darkThemeCssLink = false;
for (const htmlFile of htmlFiles) {
  let content = fs.readFileSync(htmlFile, 'utf-8');
  
  // Check if it already has dark theme link
  if (!content.includes('data-theme="dark"') && !content.includes('dark-theme-coverage')) {
    // Add dark theme class to html tag
    content = content.replace(/<html([^>]*)>/, '<html$1 data-theme="dark" class="dark-theme-coverage">');
    fs.writeFileSync(htmlFile, content);
    darkThemeCssLink = true;
  }
}

if (darkThemeCssLink) {
  console.log(`✅ Dark theme classes added to ${htmlFiles.length} HTML files`);
}

console.log('\n🎉 Coverage dark theme injection complete!');
console.log(`📁 Coverage report: ${path.resolve(coverageDir)}/index.html`);
