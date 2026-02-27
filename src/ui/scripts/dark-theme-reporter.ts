import type { Reporter, TestModule, Task, TestCase, TestSuite } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

/**
 * Custom Vitest Reporter with Dark Theme HTML Output
 * Generates dark-themed HTML report automatically during test run
 * 
 * Output: test-reports/test-results.html
 */

interface TestResult {
  name: string
  status: 'passed' | 'failed' | 'skipped'
  assertionResults: Array<{
    title: string
    status: 'passed' | 'failed' | 'skipped'
    duration?: number
    failureMessages?: string[]
  }>
}

export default class DarkThemeReporter implements Reporter {
  private startTime: number = 0
  private testResults: TestResult[] = []
  private totalTests = 0
  private passedTests = 0
  private failedTests = 0
  private skippedTests = 0

  onInit() {
    this.startTime = Date.now()
  }

  onFinished(files?: TestModule[]) {
    const endTime = Date.now()
    
    // Process all test files
    files?.forEach(file => {
      const fileResult = this.processFile(file)
      if (fileResult) {
        this.testResults.push(fileResult)
      }
    })

    // Generate the HTML report
    this.generateHTML(endTime)
  }

  private processFile(file: TestModule): TestResult | null {
    const filePath = file.moduleId || (file as any).filepath || file.id || 'unknown'
    const fileName = path.basename(String(filePath))
    
    const testCases: TestResult['assertionResults'] = []
    let fileStatus: TestResult['status'] = 'passed'

    // Walk all tasks recursively
    const walkTasks = (task: Task) => {
      if (task.type === 'test') {
        const testCase = task as TestCase
        const state = testCase.result?.state || 'skipped'
        
        this.totalTests++
        if (state === 'pass') this.passedTests++
        else if (state === 'fail') {
          this.failedTests++
          fileStatus = 'failed'
        } else {
          this.skippedTests++
        }

        // Map vitest states to our states
        const mappedState = state === 'pass' ? 'passed' : state === 'fail' ? 'failed' : 'skipped'
        
        testCases.push({
          title: this.buildTestName(testCase),
          status: mappedState,
          duration: testCase.result?.duration || 0,
          failureMessages: testCase.result?.errors?.map((e: any) => String(e.message || e)) || []
        })
      } else if (task.type === 'suite' || task.type === 'custom') {
        // Recurse into collections
        const collection = task as TestSuite
        if (collection.tasks) {
          collection.tasks.forEach(walkTasks)
        } else if ((collection as any).children) {
          (collection as any).children.forEach(walkTasks)
        }
      }
    }

    // Start from file's tasks
    const tasks = (file as any).tasks || file.children || []
    tasks.forEach(walkTasks)

    if (testCases.length === 0) return null

    return {
      name: fileName,
      status: fileStatus,
      assertionResults: testCases
    }
  }

  private buildTestName(testCase: TestCase): string {
    const parts: string[] = [testCase.name]
    
    // Walk up the parent chain
    let current: any = testCase
    while (current.parent) {
      current = current.parent
      if (current.name && current.type === 'suite') {
        parts.unshift(current.name)
      }
    }
    
    return parts.join(' > ')
  }

  private generateHTML(endTime: number) {
    const duration = ((endTime - this.startTime) / 1000).toFixed(2)
    const successRate = this.totalTests > 0 
      ? Math.round((this.passedTests / this.totalTests) * 100) 
      : 0

    const testFilesHtml = this.generateTestFilesHtml()
    
    // Get start time for display
    const startTimeStr = new Date(this.startTime).toLocaleString()

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FlexiTTS Test Results</title>
  <style>
    /* Dark Theme CSS */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #1a1a2e !important;
      color: #eaeaea !important;
      padding: 20px;
      line-height: 1.6;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    header {
      background: #16213e !important;
      padding: 30px;
      border-radius: 8px;
      border: 1px solid #0f3460 !important;
      margin-bottom: 20px;
    }
    h1 { color: #eaeaea !important; margin-bottom: 10px; }
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
    .meta { color: #a0a0a0 !important; font-size: 14px; }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin: 20px 0;
    }
    .summary-card {
      background: #16213e !important;
      padding: 20px;
      border-radius: 8px;
      border: 1px solid #0f3460 !important;
      text-align: center;
    }
    .summary-card h2 {
      font-size: 36px;
      margin-bottom: 5px;
    }
    .summary-card.passed h2 { color: #22c55e !important; }
    .summary-card.failed h2 { color: #ef4444 !important; }
    .summary-card.total h2 { color: #3b82f6 !important; }
    .summary-card.rate h2 { color: #8b5cf6 !important; }
    .summary-card p { color: #a0a0a0 !important; font-size: 14px; }
    .test-files {
      display: grid;
      gap: 15px;
    }
    .test-file {
      background: #16213e !important;
      border-radius: 8px;
      border: 1px solid #0f3460 !important;
      overflow: hidden;
    }
    .test-file.passed { border-left: 4px solid #22c55e; }
    .test-file.failed { border-left: 4px solid #ef4444; }
    .file-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px 20px;
      background: #0f3460 !important;
      border-bottom: 1px solid #0f3460;
    }
    .file-header h3 { color: #eaeaea !important; font-size: 16px; }
    .file-stats {
      background: #1a1a2e !important;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      color: #a0a0a0 !important;
    }
    .tests-list {
      padding: 15px 20px;
      background: #16213e !important;
    }
    .test-item {
      padding: 10px 0;
      border-bottom: 1px solid #0f3460;
      font-size: 14px;
      color: #eaeaea !important;
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }
    .test-item:last-child { border-bottom: none; }
    .test-icon { 
      flex-shrink: 0; 
      width: 20px;
      text-align: center;
    }
    .test-pass { color: #22c55e !important; }
    .test-fail { color: #ef4444 !important; }
    .test-skip { color: #f59e0b !important; }
    .test-title {
      flex: 1;
      word-break: break-word;
    }
    .test-duration {
      color: #6b7280;
      font-size: 12px;
      white-space: nowrap;
    }
    .footer {
      margin-top: 30px;
      padding: 20px;
      text-align: center;
      background: #16213e !important;
      border: 1px solid #0f3460 !important;
      border-radius: 8px;
      color: #a0a0a0 !important;
      font-size: 12px;
    }
    .footer p {
      color: #a0a0a0 !important;
    }
    .nav-links {
      margin-top: 15px;
    }
    .nav-links a {
      color: #4fc3f7 !important;
      text-decoration: none;
      margin: 0 10px;
    }
    .nav-links a:hover {
      color: #80d8ff !important;
      text-decoration: underline;
    }
    .error-message {
      color: #ef4444;
      font-size: 12px;
      margin-top: 4px;
      padding: 8px;
      background: rgba(239, 68, 68, 0.1);
      border-radius: 4px;
      width: 100%;
    }
    .test-content {
      flex: 1;
      display: flex;
      flex-direction: column;
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
        <p>Started: ${startTimeStr}</p>
        <p>Duration: ${duration}s</p>
      </div>
    </header>
    
    <div class="summary">
      <div class="summary-card total">
        <h2>${this.totalTests}</h2>
        <p>Total Tests</p>
      </div>
      <div class="summary-card passed">
        <h2>${this.passedTests}</h2>
        <p>Passed</p>
      </div>
      <div class="summary-card failed">
        <h2>${this.failedTests}</h2>
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
      <p>Generated by Vitest Dark Theme Reporter • FlexiTTS</p>
    </footer>
  </div>
</body>
</html>`

    // Ensure directory exists
    const outputDir = './test-reports'
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true })
    }

    const outputPath = path.join(outputDir, 'test-results.html')
    fs.writeFileSync(outputPath, html)
    
    console.log(`\n📄 Dark Theme HTML Report: ${outputPath}`)
    console.log(`   ${this.passedTests}/${this.totalTests} tests passed (${successRate}%)`)
  }

  private generateTestFilesHtml(): string {
    return this.testResults.map(file => {
      const passed = file.assertionResults.filter(t => t.status === 'passed').length
      const failed = file.assertionResults.filter(t => t.status === 'failed').length
      const total = file.assertionResults.length

      const testsList = file.assertionResults.map(test => {
        const icon = test.status === 'passed' ? '✓' : test.status === 'failed' ? '✗' : '○'
        const statusClass = test.status === 'passed' ? 'test-pass' : test.status === 'failed' ? 'test-fail' : 'test-skip'
        const duration = test.duration ? `${test.duration}ms` : ''
        
        const errorHtml = test.failureMessages && test.failureMessages.length > 0
          ? `<div class="error-message">${test.failureMessages[0]}</div>`
          : ''
        
        return `
          <div class="test-item">
            <span class="test-icon ${statusClass}">${icon}</span>
            <div class="test-content">
              <div class="test-title">${test.title}</div>
              ${errorHtml}
            </div>
            <span class="test-duration">${duration}</span>
          </div>
        `
      }).join('')

      return `
        <div class="test-file ${file.status}">
          <div class="file-header">
            <h3>${file.name}</h3>
            <span class="file-stats">${passed}/${total} passed</span>
          </div>
          <div class="tests-list">
            ${testsList}
          </div>
        </div>
      `
    }).join('')
  }
}
